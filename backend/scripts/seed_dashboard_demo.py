"""Seed the dashboard with realistic demo data for visual validation.

Inserts N projects (default 50) with varied profiles:
  - DB connector types (Postgres / MySQL / SQL Server / Snowflake / Oracle)
  - Different sizes (small / medium / large tables + column counts)
  - Different masking maturity (0 / partial / fully masked)
  - Realistic job histories spanning the last 30 days, with varied statuses

Every inserted row is tagged via the project's `settings.demo_seed` marker
(or by FK to a tagged project). `--cleanup` removes everything safely without
touching any real production data.

Usage:
  # Inside the backend container so DB hostname "postgres" resolves:
  docker compose -f docker-compose.dev.yml exec backend \
    python -m scripts.seed_dashboard_demo --seed 50

  # When done verifying the dashboard:
  docker compose -f docker-compose.dev.yml exec backend \
    python -m scripts.seed_dashboard_demo --cleanup
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.config import settings

# Importing every model module ensures SQLAlchemy can resolve foreign keys
# across the schema graph (e.g. masking_rules → generator_presets).
import app.infrastructure.persistence.models.audit  # noqa: F401
import app.infrastructure.persistence.models.compliance  # noqa: F401
import app.infrastructure.persistence.models.connection  # noqa: F401
import app.infrastructure.persistence.models.discovery  # noqa: F401
import app.infrastructure.persistence.models.ephemeral  # noqa: F401
import app.infrastructure.persistence.models.file_schema  # noqa: F401
import app.infrastructure.persistence.models.generator_preset  # noqa: F401
import app.infrastructure.persistence.models.job  # noqa: F401
import app.infrastructure.persistence.models.masking  # noqa: F401
import app.infrastructure.persistence.models.member  # noqa: F401
import app.infrastructure.persistence.models.project  # noqa: F401
import app.infrastructure.persistence.models.sensitivity_rule  # noqa: F401
import app.infrastructure.persistence.models.subsetting  # noqa: F401
import app.infrastructure.persistence.models.synthetic  # noqa: F401
import app.infrastructure.persistence.models.user  # noqa: F401
import app.infrastructure.persistence.models.webhook  # noqa: F401
import app.infrastructure.persistence.models.webhook_delivery  # noqa: F401
import app.infrastructure.persistence.models.workflow  # noqa: F401

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
from app.infrastructure.persistence.models.project import ProjectModel
from app.infrastructure.persistence.models.user import UserModel

# Marker stored in ProjectModel.settings.demo_seed — only rows with this marker
# are touched by --cleanup, so production data is never at risk.
SEED_MARKER_KEY = "demo_seed"
SEED_MARKER_VALUE = "dashboard-v1"

PROJECT_PROFILES = [
    # (name_prefix, environment, connector_type, sensitive_ratio, masking_maturity)
    # sensitive_ratio = fraction of columns that have a PII type
    # masking_maturity = fraction of sensitive columns that have an active masking rule
    # Connector values must match app.domain.connection.value_objects.ConnectorType:
    # postgresql / mysql / sqlserver / snowflake / oracle / redshift / databricks / db2 / mongodb
    ("Acme Production",          "production",  "postgresql", 0.35, 0.95),
    ("Marketing CRM",            "production",  "postgresql", 0.55, 0.40),
    ("Customer Service",         "production",  "mysql",      0.30, 0.80),
    ("Billing Platform",         "production",  "postgresql", 0.45, 1.00),
    ("Legacy Migration",         "staging",     "sqlserver",  0.60, 0.15),
    ("Mobile Analytics",         "staging",     "snowflake",  0.20, 0.55),
    ("Underwriting Sandbox",     "dev",         "postgresql", 0.50, 0.10),
    ("Quote Engine",             "production",  "postgresql", 0.40, 0.85),
    ("Claims Intake",            "production",  "oracle",     0.50, 0.70),
    ("Agent Portal",             "production",  "mysql",      0.35, 0.65),
    ("Policy Admin",             "production",  "postgresql", 0.55, 0.92),
    ("Reinsurance Hub",          "staging",     "snowflake",  0.45, 0.35),
    ("Document Imaging",         "production",  "sqlserver",  0.30, 0.50),
    ("Workflow Engine",          "production",  "postgresql", 0.25, 0.60),
    ("Risk Modelling",           "dev",         "snowflake",  0.40, 0.20),
    ("Audit Warehouse",          "production",  "postgresql", 0.65, 1.00),
    ("Provider Network",         "production",  "mysql",      0.35, 0.45),
    ("Disability Claims",        "production",  "postgresql", 0.55, 0.80),
    ("Group Benefits",           "production",  "postgresql", 0.50, 0.70),
    ("Annuity Service",          "production",  "oracle",     0.45, 0.65),
]

# Realistic PII type vocabulary the discovery service classifies into.
PII_TYPES = ["email", "phone", "ssn", "address", "name", "dob", "credit_card", "ip_address"]
NON_PII_TYPES = ["none"]
# Must match app.domain.shared.job.JobType values exactly — the API rehydrates
# strings into the enum, and an unknown value raises ValueError.
JOB_TYPES = ["discovery", "masking", "generation", "subsetting", "compliance", "workflow"]
JOB_STATUSES_WEIGHTED = (
    ["completed"] * 16
    + ["failed"] * 2
    + ["running"] * 1
    + ["cancelled"] * 1
)

TABLE_NAMES = [
    "customers", "orders", "payments", "users", "addresses", "transactions",
    "policies", "claims", "agents", "vendors", "products", "audit_log",
    "sessions", "billing_history", "contacts", "documents", "events",
    "subscriptions", "invoices", "members",
]

COLUMN_NAME_POOLS = {
    "email": ["email", "email_address", "contact_email", "alt_email"],
    "phone": ["phone", "phone_number", "mobile", "telephone"],
    "ssn": ["ssn", "tax_id", "social_security_number"],
    "address": ["address_line_1", "street_address", "mailing_address"],
    "name": ["full_name", "first_name", "last_name", "given_name", "surname"],
    "dob": ["dob", "date_of_birth", "birthdate"],
    "credit_card": ["card_number", "cc_number", "payment_method_number"],
    "ip_address": ["ip_address", "last_login_ip", "source_ip"],
    "none": ["id", "created_at", "updated_at", "status", "amount", "currency", "quantity", "notes", "is_active", "score"],
}


def _engine():
    url = settings.DATABASE_URL_SYNC
    if not url:
        raise SystemExit("DATABASE_URL_SYNC is not configured")
    return create_engine(url, future=True)


def _pick_user(session: Session) -> UserModel:
    """Pick the first existing user; fall back to creating a demo service user."""
    user = session.execute(select(UserModel).limit(1)).scalar_one_or_none()
    if user is not None:
        return user
    user = UserModel(
        email="demo-seed@datawrangler.local",
        full_name="Demo Seed Service",
        role="admin",
    )
    session.add(user)
    session.flush()
    return user


def _seeded_project_ids(session: Session) -> list[uuid.UUID]:
    rows = session.execute(
        select(ProjectModel.id).where(
            ProjectModel.settings[SEED_MARKER_KEY].as_string() == SEED_MARKER_VALUE,
        ),
    ).all()
    return [r[0] for r in rows]


def cleanup(session: Session) -> int:
    """Delete every seeded project plus its dependent rows. Returns project count removed."""
    project_ids = _seeded_project_ids(session)
    if not project_ids:
        return 0
    # Manual FK-respecting delete order — relying on cascades isn't safe across all envs.
    conn_ids = [
        r[0]
        for r in session.execute(
            select(ConnectionModel.id).where(ConnectionModel.project_id.in_(project_ids)),
        ).all()
    ]
    schema_ids = (
        [
            r[0]
            for r in session.execute(
                select(DiscoveredSchemaModel.id).where(
                    DiscoveredSchemaModel.connection_id.in_(conn_ids),
                ),
            ).all()
        ]
        if conn_ids
        else []
    )
    table_ids = (
        [
            r[0]
            for r in session.execute(
                select(DiscoveredTableModel.id).where(
                    DiscoveredTableModel.schema_id.in_(schema_ids),
                ),
            ).all()
        ]
        if schema_ids
        else []
    )
    policy_ids = [
        r[0]
        for r in session.execute(
            select(MaskingPolicyModel.id).where(
                MaskingPolicyModel.project_id.in_(project_ids),
            ),
        ).all()
    ]

    if table_ids:
        session.execute(
            delete(DiscoveredColumnModel).where(DiscoveredColumnModel.table_id.in_(table_ids)),
        )
        session.execute(delete(DiscoveredTableModel).where(DiscoveredTableModel.id.in_(table_ids)))
    if schema_ids:
        session.execute(
            delete(DiscoveredSchemaModel).where(DiscoveredSchemaModel.id.in_(schema_ids)),
        )
    if policy_ids:
        session.execute(delete(MaskingRuleModel).where(MaskingRuleModel.policy_id.in_(policy_ids)))
        session.execute(delete(MaskingPolicyModel).where(MaskingPolicyModel.id.in_(policy_ids)))
    if conn_ids:
        session.execute(delete(ConnectionModel).where(ConnectionModel.id.in_(conn_ids)))
    session.execute(delete(JobModel).where(JobModel.project_id.in_(project_ids)))
    session.execute(delete(ProjectModel).where(ProjectModel.id.in_(project_ids)))
    session.commit()
    return len(project_ids)


def seed(session: Session, count: int) -> int:
    """Insert `count` demo projects with varied profiles. Idempotent: cleans up first."""
    cleanup(session)
    user = _pick_user(session)
    now = datetime.now(timezone.utc)

    created = 0
    for i in range(count):
        profile = PROJECT_PROFILES[i % len(PROJECT_PROFILES)]
        name_prefix, environment, connector, sens_ratio, masking_maturity = profile
        # Suffix so re-runs produce unique names even if cleanup hadn't happened.
        suffix = "" if i < len(PROJECT_PROFILES) else f" {i // len(PROJECT_PROFILES) + 1}"
        name = f"{name_prefix}{suffix}"
        created_at = now - timedelta(days=random.randint(7, 120))
        updated_at = now - timedelta(hours=random.randint(0, 240))

        project = ProjectModel(
            name=name,
            description=f"{environment.capitalize()} {connector} workload — demo seed",
            owner_id=user.id,
            settings={
                "environment": environment,
                "connector_hint": connector,
                SEED_MARKER_KEY: SEED_MARKER_VALUE,
            },
        )
        # Override timestamps after add to backdate.
        project.created_at = created_at
        project.updated_at = updated_at
        session.add(project)
        session.flush()

        # ── Connection ───────────────────────────────────────────────────
        port_by_type = {
            "postgresql": 5432,
            "mysql": 3306,
            "sqlserver": 1433,
            "snowflake": 443,
            "oracle": 1521,
        }
        # ConnectionStatus values: connected / failed / untested / disabled.
        # Weight toward connected so most projects look "healthy".
        status = random.choices(
            ["connected", "untested", "failed", "disabled"],
            weights=[8, 2, 1, 1],
            k=1,
        )[0]
        connection = ConnectionModel(
            project_id=project.id,
            name=f"{connector}-{environment}",
            connector_type=connector,
            host=f"demo-{connector}.internal",
            port=port_by_type.get(connector, 5432),
            database_name=f"{name_prefix.lower().replace(' ', '_')}_db",
            credentials={"_encrypted": "demo"},
            status=status,
            # Spread last_tested_at across last 21 days so the "stale connection"
            # insight fires for some projects.
            last_tested_at=now - timedelta(days=random.randint(0, 21)),
        )
        session.add(connection)
        session.flush()

        # ── Schema + tables + columns ────────────────────────────────────
        schema = DiscoveredSchemaModel(
            connection_id=connection.id,
            schema_name="public",
            discovered_at=now - timedelta(days=random.randint(0, 30)),
        )
        session.add(schema)
        session.flush()

        # 5–15 tables per project
        n_tables = random.randint(5, 15)
        sensitive_col_ids: list[uuid.UUID] = []
        for tname in random.sample(TABLE_NAMES, k=min(n_tables, len(TABLE_NAMES))):
            table = DiscoveredTableModel(
                schema_id=schema.id,
                table_name=tname,
                # row_count and size_bytes are 32-bit ints in the schema —
                # keep values below 2_147_483_647 (Postgres INTEGER max).
                row_count=random.randint(100, 5_000_000),
                size_bytes=random.randint(10_000, 2_000_000_000),
            )
            session.add(table)
            session.flush()

            # 5–20 columns per table
            n_cols = random.randint(5, 20)
            for c in range(n_cols):
                is_sensitive = random.random() < sens_ratio
                pii_type = (
                    random.choice(PII_TYPES) if is_sensitive else random.choice(NON_PII_TYPES)
                )
                col_name = random.choice(COLUMN_NAME_POOLS[pii_type])
                # Make column names unique within a table
                col_name = f"{col_name}_{c}" if c > 0 else col_name
                col = DiscoveredColumnModel(
                    table_id=table.id,
                    column_name=col_name,
                    data_type="varchar" if is_sensitive else "integer",
                    is_nullable=True,
                    is_primary_key=(c == 0 and not is_sensitive),
                    pii_type=pii_type,
                    pii_confidence={"score": round(random.uniform(0.7, 0.99), 2)}
                    if is_sensitive
                    else None,
                    classification="classified" if is_sensitive else "needs_review",
                )
                session.add(col)
                if is_sensitive:
                    session.flush()
                    sensitive_col_ids.append(col.id)

        # ── Masking policy + rules covering some sensitive columns ───────
        if sensitive_col_ids and masking_maturity > 0:
            policy = MaskingPolicyModel(
                project_id=project.id,
                name="Default PII protection",
                description="Demo seed policy",
                is_default=True,
            )
            session.add(policy)
            session.flush()
            n_to_protect = int(len(sensitive_col_ids) * masking_maturity)
            for col_id in random.sample(sensitive_col_ids, k=n_to_protect):
                session.add(
                    MaskingRuleModel(
                        policy_id=policy.id,
                        column_id=col_id,
                        # Must match app.domain.masking.value_objects.MaskingStrategy values.
                        masking_type=random.choice(
                            ["redact", "hash", "faker_replace", "partial_mask", "fpe"],
                        ),
                    ),
                )

        # ── Jobs spanning last 30 days ───────────────────────────────────
        n_jobs = random.randint(0, 40)
        for _ in range(n_jobs):
            jstatus = random.choice(JOB_STATUSES_WEIGHTED)
            jcreated = now - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            jstarted = jcreated + timedelta(seconds=random.randint(1, 60)) if jstatus != "pending" else None
            jcompleted = None
            if jstatus in {"completed", "failed", "cancelled"}:
                jcompleted = (jstarted or jcreated) + timedelta(
                    seconds=random.randint(30, 1800)
                )
            session.add(
                JobModel(
                    project_id=project.id,
                    job_type=random.choice(JOB_TYPES),
                    reference_id=uuid.uuid4(),
                    status=jstatus,
                    progress=100 if jstatus in {"completed", "failed"} else random.randint(0, 90),
                    created_by=user.id,
                    started_at=jstarted,
                    completed_at=jcompleted,
                ),
            )

        created += 1

    session.commit()
    return created


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--seed", type=int, metavar="N", help="Insert N demo projects (default 50)")
    g.add_argument("--cleanup", action="store_true", help="Remove all seeded projects")
    g.add_argument("--count", action="store_true", help="Report how many seeded projects exist")
    args = ap.parse_args()

    random.seed(42)  # Reproducible runs
    engine = _engine()
    with Session(engine) as session:
        if args.cleanup:
            n = cleanup(session)
            print(f"Removed {n} seeded projects (and all dependent rows).")
            return 0
        if args.count:
            n = len(_seeded_project_ids(session))
            print(f"{n} seeded project(s) currently in the database.")
            return 0
        if args.seed is not None:
            target = args.seed if args.seed > 0 else 50
            n = seed(session, target)
            print(f"Seeded {n} demo projects with connections, schemas, columns, policies, jobs.")
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
