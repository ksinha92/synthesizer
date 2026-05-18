"""Privacy Hub aggregate + bulk-apply endpoints (Phase 49)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.connection import ConnectionModel
from app.infrastructure.persistence.models.discovery import (
    DiscoveredColumnModel,
    DiscoveredSchemaModel,
    DiscoveredTableModel,
)
from app.infrastructure.persistence.models.job import JobModel
from app.infrastructure.persistence.models.masking import (
    MaskingPolicyModel,
    MaskingRuleModel,
)
from app.infrastructure.persistence.sqlalchemy.connection_repo import (
    SQLAlchemyConnectionRepository,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}/privacy-hub",
    tags=["privacy-hub"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


# Default generator suggestion per PII type. Conservative: hash for true secrets,
# faker_replace for human-readable PII, redact for unclassified sensitive values.
DEFAULT_GENERATOR_BY_PII: dict[str, str] = {
    "email": "faker_replace",
    "phone": "faker_replace",
    "ssn": "hash",
    "person_name": "faker_replace",
    "address": "faker_replace",
    "credit_card": "hash",
    "ip_address": "faker_replace",
    "date_of_birth": "faker_replace",
    "financial_account": "hash",
    "medical_record": "hash",
}

# Label shown in the UI for each PII type.
PII_LABELS: dict[str, str] = {
    "email": "Email",
    "phone": "Phone",
    "ssn": "SSN",
    "person_name": "Name",
    "address": "Address",
    "credit_card": "Credit Card",
    "ip_address": "IP Address",
    "date_of_birth": "Date of Birth",
    "financial_account": "Financial Account",
    "medical_record": "Medical Record",
}


class TableBreakdownRow(BaseModel):
    """Per-table summary surfaced by the Privacy Hub Database Tables view.

    Mirrors Tonic's screenshot 11.29.48 columns — table name, count of PII
    columns, count of formatted/redacted (i.e. covered by at least one
    masking rule), and a 0-100 privacy rating derived from
    ``protected_columns / sensitive_columns``.
    """

    schema_name: str
    table_name: str
    total_columns: int
    sensitive_columns: int
    protected_columns: int
    privacy_rating: int  # 0-100 protected % of sensitive columns


class PrivacyHubResponse(BaseModel):
    sensitive_count: int
    protected_count: int
    unprotected_count: int
    recommendations: list[dict]
    tables: list[TableBreakdownRow] = []


class ApplyAllRequest(BaseModel):
    pii_types: list[str]


class ApplyAllResponse(BaseModel):
    rules_created: int
    policy_id: str
    job_id: str | None = None
    note: str | None = None


async def _project_sensitive_columns(
    session: AsyncSession, project_id: uuid.UUID
) -> list[tuple[uuid.UUID, str]]:
    """All sensitive columns in the project (pii_type != 'none').

    Returns list of (column_id, pii_type) tuples.
    """
    query = (
        select(DiscoveredColumnModel.id, DiscoveredColumnModel.pii_type)
        .join(
            DiscoveredTableModel,
            DiscoveredTableModel.id == DiscoveredColumnModel.table_id,
        )
        .join(
            DiscoveredSchemaModel,
            DiscoveredSchemaModel.id == DiscoveredTableModel.schema_id,
        )
        .join(
            ConnectionModel,
            ConnectionModel.id == DiscoveredSchemaModel.connection_id,
        )
        .where(
            ConnectionModel.project_id == project_id,
            DiscoveredColumnModel.pii_type != "none",
        )
    )
    result = await session.execute(query)
    return [(row[0], row[1]) for row in result.all()]


async def _project_table_breakdown(
    session: AsyncSession,
    project_id: uuid.UUID,
    protected_ids: set[uuid.UUID],
) -> list[TableBreakdownRow]:
    """Per-table privacy summary for the Privacy Hub Database Tables view.

    Joins every column in the project up through table → schema → connection.
    Counts run client-side so we keep one round-trip; the rows-per-project
    cap is bounded by discovery (typically hundreds, not millions).
    """
    query = (
        select(
            DiscoveredSchemaModel.schema_name,
            DiscoveredTableModel.table_name,
            DiscoveredColumnModel.id,
            DiscoveredColumnModel.pii_type,
        )
        .join(
            DiscoveredTableModel,
            DiscoveredTableModel.id == DiscoveredColumnModel.table_id,
        )
        .join(
            DiscoveredSchemaModel,
            DiscoveredSchemaModel.id == DiscoveredTableModel.schema_id,
        )
        .join(
            ConnectionModel,
            ConnectionModel.id == DiscoveredSchemaModel.connection_id,
        )
        .where(ConnectionModel.project_id == project_id)
    )
    result = await session.execute(query)

    # bucket: (schema, table) → {total, sensitive, protected}
    buckets: dict[tuple[str, str], dict[str, int]] = {}
    for schema_name, table_name, col_id, pii in result.all():
        key = (schema_name, table_name)
        b = buckets.setdefault(
            key, {"total": 0, "sensitive": 0, "protected": 0}
        )
        b["total"] += 1
        if pii and pii != "none":
            b["sensitive"] += 1
            if col_id in protected_ids:
                b["protected"] += 1

    rows: list[TableBreakdownRow] = []
    for (schema_name, table_name), b in buckets.items():
        sensitive = b["sensitive"]
        protected = b["protected"]
        rating = 100 if sensitive == 0 else int(round((protected / sensitive) * 100))
        rows.append(
            TableBreakdownRow(
                schema_name=schema_name,
                table_name=table_name,
                total_columns=b["total"],
                sensitive_columns=sensitive,
                protected_columns=protected,
                privacy_rating=rating,
            )
        )
    # Sort: most-at-risk first (lowest privacy_rating with sensitive>0), then
    # by table name. Tables with no PII fall to the bottom.
    rows.sort(
        key=lambda r: (
            r.sensitive_columns == 0,
            r.privacy_rating,
            r.schema_name,
            r.table_name,
        )
    )
    return rows


async def _project_protected_column_ids(
    session: AsyncSession, project_id: uuid.UUID
) -> set[uuid.UUID]:
    """Set of column IDs that already have at least one masking rule in this project."""
    query = (
        select(MaskingRuleModel.column_id)
        .join(
            MaskingPolicyModel,
            MaskingPolicyModel.id == MaskingRuleModel.policy_id,
        )
        .where(
            MaskingPolicyModel.project_id == project_id,
            MaskingRuleModel.column_id.is_not(None),
        )
    )
    result = await session.execute(query)
    return {row[0] for row in result.all() if row[0] is not None}


@router.get("", response_model=PrivacyHubResponse)
async def get_privacy_hub(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Aggregate counters + recommended-generator groups for the project."""
    sensitive = await _project_sensitive_columns(session, project_id)
    protected_ids = await _project_protected_column_ids(session, project_id)

    sensitive_count = len(sensitive)
    protected_count = sum(1 for col_id, _ in sensitive if col_id in protected_ids)
    unprotected_count = sensitive_count - protected_count

    # Group unprotected columns by PII type.
    unprotected_by_pii: dict[str, int] = {}
    for col_id, pii in sensitive:
        if col_id in protected_ids:
            continue
        unprotected_by_pii[pii] = unprotected_by_pii.get(pii, 0) + 1

    recommendations = [
        {
            "pii_type": pii,
            "label": PII_LABELS.get(pii, pii.replace("_", " ").title()),
            "unprotected_columns": count,
            "recommended_generator": DEFAULT_GENERATOR_BY_PII.get(pii, "redact"),
        }
        for pii, count in sorted(
            unprotected_by_pii.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]

    tables = await _project_table_breakdown(session, project_id, protected_ids)

    return PrivacyHubResponse(
        sensitive_count=sensitive_count,
        protected_count=protected_count,
        unprotected_count=unprotected_count,
        recommendations=recommendations,
        tables=tables,
    )


@router.post("/apply-all", response_model=ApplyAllResponse, status_code=201)
async def apply_all(
    project_id: uuid.UUID,
    body: ApplyAllRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Bulk-create masking rules for unprotected columns of the requested PII types.

    Idempotent: columns that already have a matching rule are skipped.
    Creates (or reuses) a "Default" policy for the project to hold the rules.
    """
    if not body.pii_types:
        raise HTTPException(
            400, {"error": "no_pii_types", "detail": "pii_types must not be empty"}
        )

    sensitive = await _project_sensitive_columns(session, project_id)
    protected_ids = await _project_protected_column_ids(session, project_id)
    targets = [
        (col_id, pii)
        for col_id, pii in sensitive
        if pii in body.pii_types and col_id not in protected_ids
    ]

    if not targets:
        # Nothing to do — still return a 201 with rules_created=0 and a policy id
        # so the UI can react uniformly.
        policy_id = await _get_or_create_default_policy(session, project_id)
        return ApplyAllResponse(rules_created=0, policy_id=str(policy_id))

    policy_id = await _get_or_create_default_policy(session, project_id)

    created = 0
    for col_id, pii in targets:
        masking_type = DEFAULT_GENERATOR_BY_PII.get(pii, "redact")
        rule = MaskingRuleModel(
            id=uuid.uuid4(),
            policy_id=policy_id,
            column_id=col_id,
            match_pattern=None,
            masking_type=masking_type,
            masking_config={},
            preserve_format=False,
            deterministic=False,
        )
        session.add(rule)
        created += 1

    await session.flush()

    # F3 (Phase 57): rule rows alone don't mask data. Enqueue run_masking_task
    # against the project's first available connection so the policy actually
    # runs end-to-end. If the project has no connection yet, surface that to
    # the caller via `note` instead of failing — the rules are still useful
    # once a connection is wired up later.
    job_id: str | None = None
    note: str | None = None
    connection_repo = SQLAlchemyConnectionRepository(session)
    connections = await connection_repo.find_by_project_id(project_id, limit=1)
    if not connections:
        note = "no_connection_to_mask"
    else:
        connection = connections[0]
        user_id_raw = current_user.get("id")
        created_by = (
            uuid.UUID(user_id_raw)
            if user_id_raw
            else uuid.UUID("00000000-0000-0000-0000-000000000000")
        )
        # Pre-assign the job UUID so we can hand it to the Celery task even
        # if the SQLAlchemy default hasn't materialised the column yet
        # (matches the pattern used for MaskingRuleModel above).
        job = JobModel(
            id=uuid.uuid4(),
            project_id=project_id,
            job_type="masking",
            reference_id=policy_id,
            status="pending",
            progress=0,
            created_by=created_by,
        )
        session.add(job)
        await session.flush()

        from app.infrastructure.messaging.masking_tasks import run_masking_task

        run_masking_task.delay(
            str(policy_id),
            str(connection.id),
            str(project_id),
            str(job.id),
        )
        job_id = str(job.id)

    await logger.ainfo(
        "privacy_hub_apply_all",
        project_id=str(project_id),
        rules_created=created,
        pii_types=body.pii_types,
        user_id=current_user.get("id"),
        job_id=job_id,
        note=note,
    )

    return ApplyAllResponse(
        rules_created=created,
        policy_id=str(policy_id),
        job_id=job_id,
        note=note,
    )


# Default-policy lookup lives in _masking_common so the Database View can
# share it without reaching across router boundaries. Re-exported here under
# its original underscore name so existing callers in this module keep working.
from app.api.v1._masking_common import (  # noqa: E402
    get_or_create_default_policy as _get_or_create_default_policy,
)
