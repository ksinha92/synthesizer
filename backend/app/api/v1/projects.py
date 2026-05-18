"""Project CRUD API endpoints."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import assert_project_access
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.project import ProjectModel

logger = structlog.get_logger()

router = APIRouter(prefix="/projects", tags=["projects"])


# --- Request/Response Models ---


class InitialConnectionPayload(BaseModel):
    """Connection payload accepted alongside a project create.

    Intentionally mirrors ``ConnectionCreate`` from ``connections.py`` —
    duplicated here so this module doesn't have to import the connections
    router at load time. Keep field names in sync; the wizard contract test
    in ``tests/integration/test_api_projects.py`` guards them.
    """

    name: str
    connector_type: str
    host: str
    port: int
    database_name: str
    username: str = ""
    password: str = ""
    extra_params: dict = Field(default_factory=dict)


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    settings: dict | None = None
    # New Project Wizard support — both are optional so the existing
    # one-shot create-without-connection call site keeps working.
    initial_connection: InitialConnectionPayload | None = None
    run_discovery: bool = False


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    settings: dict | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    owner_id: str
    settings: dict | None
    created_at: str
    updated_at: str
    # Set only when the wizard created a connection inline. Null for the
    # legacy "project only" create call.
    connection_id: str | None = None
    # Set only when the wizard enqueued a discovery job. Null otherwise.
    discovery_job_id: str | None = None


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total_count: int
    page: int
    page_size: int
    has_more: bool


# --- Endpoints ---


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a project, optionally with an initial connection + discovery job.

    Three call shapes are supported (all atomic — the whole tree commits
    or nothing does):

    * Bare project (legacy): ``{"name": "..."}``
    * Project + connection (New Project Wizard): includes ``initial_connection``
    * Project + connection + discovery: also passes ``run_discovery=true``

    If ``initial_connection`` is invalid (bad creds / unsupported connector)
    the project insert is rolled back so the user doesn't end up with an
    orphan empty project. Discovery is queued *after* the commit so a Celery
    enqueue failure can't break the create itself.
    """
    project = ProjectModel(
        name=body.name,
        description=body.description,
        owner_id=uuid.UUID(current_user["id"]),
        settings=body.settings or {},
    )
    session.add(project)
    await session.flush()

    connection_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None

    if body.initial_connection is not None:
        # Re-use the existing CreateConnectionHandler so encryption,
        # connector-type validation, and the domain event path stay in
        # one place. The handler shares this session, so a failure here
        # raises out and rolls the project insert back together with the
        # connection insert.
        from app.application.connection.commands import CreateConnectionCommand
        from app.application.connection.handlers import CreateConnectionHandler
        from app.infrastructure.persistence.sqlalchemy.connection_repo import (
            SQLAlchemyConnectionRepository,
        )

        try:
            handler = CreateConnectionHandler(
                SQLAlchemyConnectionRepository(session)
            )
            connection = await handler.handle(
                CreateConnectionCommand(
                    project_id=project.id,
                    name=body.initial_connection.name,
                    connector_type=body.initial_connection.connector_type,
                    host=body.initial_connection.host,
                    port=body.initial_connection.port,
                    database_name=body.initial_connection.database_name,
                    username=body.initial_connection.username,
                    password=body.initial_connection.password,
                    extra_params=body.initial_connection.extra_params,
                )
            )
            connection_id = connection.id
        except Exception as exc:
            await session.rollback()
            await logger.awarning(
                "project_wizard_connection_failed",
                user_id=current_user["id"],
                error=type(exc).__name__,
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "initial_connection_failed",
                    "detail": f"Could not create initial connection: {exc}",
                },
            )

        # Optional discovery enqueue. Done before commit so the JobModel
        # row participates in the same transaction; Celery dispatch happens
        # after commit (otherwise a worker could race and read the job row
        # before it's visible).
        if body.run_discovery:
            from app.infrastructure.persistence.models.job import JobModel

            job = JobModel(
                project_id=project.id,
                job_type="discovery",
                reference_id=connection_id,
                status="pending",
                progress=0,
                created_by=uuid.UUID(current_user["id"]),
            )
            session.add(job)
            await session.flush()
            job_id = job.id

    # Commit (or roll back) the full tree, then enqueue Celery.
    await session.commit()

    if job_id is not None and connection_id is not None:
        try:
            from app.infrastructure.messaging.discovery_tasks import run_discovery_task

            run_discovery_task.delay(
                str(connection_id), str(project.id), str(job_id)
            )
        except Exception as exc:
            # The project + connection + job row are already committed.
            # Surface the dispatch failure as 202-ish so the user knows the
            # project exists but the job didn't fire.
            await logger.aerror(
                "project_wizard_discovery_dispatch_failed",
                project_id=str(project.id),
                connection_id=str(connection_id),
                job_id=str(job_id),
                error=type(exc).__name__,
            )
            # Don't fail the whole request — caller can retry from the UI.

    await logger.ainfo(
        "project_created",
        project_id=str(project.id),
        user_id=current_user["id"],
        with_connection=connection_id is not None,
        with_discovery=job_id is not None,
    )

    response = _project_response(project)
    if connection_id is not None:
        response.connection_id = str(connection_id)
    if job_id is not None:
        response.discovery_job_id = str(job_id)
    return response


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    page: int = 1,
    page_size: int = 50,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * page_size
    owner_id = uuid.UUID(current_user["id"])

    result = await session.execute(
        select(ProjectModel)
        .where(ProjectModel.owner_id == owner_id)
        .order_by(ProjectModel.updated_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    projects = result.scalars().all()

    count_result = await session.execute(
        select(func.count()).select_from(ProjectModel).where(ProjectModel.owner_id == owner_id)
    )
    total = count_result.scalar_one()

    return ProjectListResponse(
        items=[_project_response(p) for p in projects],
        total_count=total,
        page=page,
        page_size=page_size,
        has_more=(offset + page_size) < total,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await assert_project_access(project_id, current_user, session, "viewer")
    project = await _get_project_or_404(session, project_id)
    return _project_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await assert_project_access(project_id, current_user, session, "editor")
    project = await _get_project_or_404(session, project_id)

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.settings is not None:
        project.settings = body.settings

    await session.flush()
    return _project_response(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Destructive — owners and system admins only (project "admin" members
    # don't include the owner record itself, so we keep the owner-or-admin
    # ladder here and don't accept editor/viewer members).
    project = await _get_owned_project(session, project_id, current_user)
    await session.execute(delete(ProjectModel).where(ProjectModel.id == project.id))
    await logger.ainfo("project_deleted", project_id=str(project_id), user_id=current_user["id"])


# --- Child Workspace clone (T3.2, Tonic 11.22.08) --------------------------


class CloneProjectRequest(BaseModel):
    """Optional overrides for the cloned project's name + description.
    Defaults to ``"<parent name> (copy)"`` and the parent's description."""

    name: str | None = None
    description: str | None = None


@router.post(
    "/{project_id}/clone",
    response_model=ProjectResponse,
    status_code=201,
)
async def clone_project(
    project_id: uuid.UUID,
    body: CloneProjectRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a child workspace seeded from this project's configuration.

    Copies:
      * connections (encrypted credentials carry over verbatim because the
        Fernet key is process-wide).
      * masking policies + rules (column references stay pointing at the
        parent's discovery snapshot — rerunning discovery on the child
        decouples them).
      * webhooks (URL + events + secret hash).

    NOT cloned: discovered_schemas / tables / columns, job history, subset
    configs. Generator presets and sensitivity rules already live globally.
    """
    from app.infrastructure.persistence.models.connection import ConnectionModel
    from app.infrastructure.persistence.models.masking import (
        MaskingPolicyModel,
        MaskingRuleModel,
    )
    from app.infrastructure.persistence.models.webhook import WebhookModel

    # Cloning creates a brand new project owned by the caller — they must
    # have at least viewer access on the source to read its config.
    await assert_project_access(project_id, current_user, session, "viewer")
    parent = await _get_project_or_404(session, project_id)

    child = ProjectModel(
        name=(body.name or f"{parent.name} (copy)").strip(),
        description=body.description if body.description is not None else parent.description,
        owner_id=uuid.UUID(current_user["id"]),
        settings=dict(parent.settings or {}),
    )
    session.add(child)
    await session.flush()

    # Connections — column-for-column copy under the new project_id.
    conn_rows = await session.execute(
        select(ConnectionModel).where(ConnectionModel.project_id == project_id)
    )
    cloned_connections = 0
    for conn in conn_rows.scalars().all():
        session.add(
            ConnectionModel(
                id=uuid.uuid4(),
                project_id=child.id,
                name=conn.name,
                connector_type=conn.connector_type,
                host=conn.host,
                port=conn.port,
                database_name=conn.database_name,
                credentials=conn.credentials,
                extra_params=conn.extra_params,
            )
        )
        cloned_connections += 1

    # Masking policies + rules.
    policy_rows = await session.execute(
        select(MaskingPolicyModel).where(MaskingPolicyModel.project_id == project_id)
    )
    cloned_rules = 0
    for policy in policy_rows.scalars().all():
        new_policy = MaskingPolicyModel(
            id=uuid.uuid4(),
            project_id=child.id,
            name=policy.name,
            description=policy.description,
            is_default=policy.is_default,
        )
        session.add(new_policy)
        await session.flush()

        rule_rows = await session.execute(
            select(MaskingRuleModel).where(MaskingRuleModel.policy_id == policy.id)
        )
        for rule in rule_rows.scalars().all():
            session.add(
                MaskingRuleModel(
                    id=uuid.uuid4(),
                    policy_id=new_policy.id,
                    column_id=rule.column_id,
                    match_pattern=rule.match_pattern,
                    masking_type=rule.masking_type,
                    masking_config=rule.masking_config,
                    preserve_format=rule.preserve_format,
                    deterministic=rule.deterministic,
                )
            )
            cloned_rules += 1

    # Webhooks.
    hook_rows = await session.execute(
        select(WebhookModel).where(WebhookModel.project_id == project_id)
    )
    cloned_hooks = 0
    for hook in hook_rows.scalars().all():
        # Copy both signing surfaces so a post-F14 webhook (raw-secret HMAC)
        # keeps verifying after clone. Dropping `secret_encrypted` here would
        # silently downgrade the clone to the legacy signing path.
        session.add(
            WebhookModel(
                id=uuid.uuid4(),
                project_id=child.id,
                url=hook.url,
                events=hook.events,
                secret_hash=hook.secret_hash,
                secret_encrypted=hook.secret_encrypted,
                legacy_signing=hook.legacy_signing,
                is_active=hook.is_active,
            )
        )
        cloned_hooks += 1

    await session.commit()

    await logger.ainfo(
        "project_cloned",
        parent_id=str(project_id),
        child_id=str(child.id),
        connections=cloned_connections,
        rules=cloned_rules,
        webhooks=cloned_hooks,
        user_id=current_user["id"],
    )

    return _project_response(child)


# --- Helpers ---


async def _get_owned_project(
    session: AsyncSession, project_id: uuid.UUID, current_user: dict
) -> ProjectModel:
    """Strict ownership check — owner or system admin only.

    Used by destructive endpoints (delete) where members shouldn't be able
    to operate even if they're project admins. Membership-permissive checks
    use ``assert_project_access`` instead.
    """
    project = await _get_project_or_404(session, project_id)
    if str(project.owner_id) != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail={"error": "forbidden", "detail": "Not your project"})
    return project


async def _get_project_or_404(
    session: AsyncSession, project_id: uuid.UUID
) -> ProjectModel:
    result = await session.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Project not found"})
    return project


def _project_response(project: ProjectModel) -> ProjectResponse:
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        owner_id=str(project.owner_id),
        settings=project.settings,
        created_at=project.created_at.isoformat() if project.created_at else "",
        updated_at=project.updated_at.isoformat() if project.updated_at else "",
    )
