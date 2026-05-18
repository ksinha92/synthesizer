"""Synthetic data generation API endpoints.

Holds the *core* config / preview / generate / NLP / quality surface. File-
schema and file-set endpoints were extracted to ``synthetic_file_schemas.py``
in Phase 61 (F19) — both routers share the
``/projects/{project_id}/synthetic`` prefix when mounted.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.synthetic.commands import (
    CreateSyntheticConfigCommand,
    GenerateCommand,
    PreviewCommand,
)
from app.application.synthetic.handlers import (
    CreateConfigHandler,
    GenerateHandler,
    GetConfigHandler,
    ListConfigsHandler,
    PreviewHandler,
)
from app.application.synthetic.queries import GetConfigQuery, ListConfigsQuery
from app.domain.shared.errors import NotFoundError
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.synthetic_repo import SQLAlchemySyntheticRepository

logger = structlog.get_logger()

router = APIRouter(
    prefix="/projects/{project_id}/synthetic",
    tags=["synthetic"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


# --- Request/Response Models ---


ALLOWED_OUTPUT_MODES = {"same_database", "different_connection", "download_zip", "s3"}


class ConfigCreate(BaseModel):
    name: str
    source_connection_id: str
    generation_method: str = "faker"
    tables: list[dict] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    nlp_prompt: str | None = None
    row_count: int = 100
    output_mode: str = "same_database"


class ConfigResponse(BaseModel):
    id: str
    name: str
    source_connection_id: str | None = None
    generation_method: str
    row_count: int
    status: str
    output_mode: str = "same_database"
    created_at: str


class PreviewRequest(BaseModel):
    config_id: str
    limit: int = 10


class GenerateRequest(BaseModel):
    config_id: str


class GenerateResponse(BaseModel):
    job_id: str
    status: str = "pending"


# --- Endpoints ---


@router.post("/configs", response_model=ConfigResponse, status_code=201)
async def create_config(
    project_id: uuid.UUID,
    body: ConfigCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemySyntheticRepository(session)
    handler = CreateConfigHandler(repo)

    config = await handler.handle(
        CreateSyntheticConfigCommand(
            project_id=project_id,
            name=body.name,
            source_connection_id=uuid.UUID(body.source_connection_id),
            generation_method=body.generation_method,
            tables=body.tables,
            config=body.config,
            nlp_prompt=body.nlp_prompt,
            row_count=body.row_count,
        )
    )

    await logger.ainfo(
        "synthetic_config_created",
        config_id=str(config.id),
        project_id=str(project_id),
        user_id=current_user["id"],
        ip=request.client.host if request.client else "unknown",
    )

    # If the request specified a non-default output_mode, apply via direct
    # update (the domain command pipeline doesn't carry this field yet).
    if body.output_mode != "same_database":
        if body.output_mode not in ALLOWED_OUTPUT_MODES:
            raise HTTPException(
                400,
                {
                    "error": "invalid_output_mode",
                    "detail": f"output_mode must be one of {sorted(ALLOWED_OUTPUT_MODES)}",
                },
            )
        from sqlalchemy import update as _update
        from app.infrastructure.persistence.models.synthetic import SyntheticConfigModel
        await session.execute(
            _update(SyntheticConfigModel)
            .where(SyntheticConfigModel.id == config.id)
            .values(output_mode=body.output_mode)
        )
        await session.flush()
        output_mode = body.output_mode
    else:
        output_mode = "same_database"

    return ConfigResponse(
        id=str(config.id),
        name=config.name,
        source_connection_id=str(config.source_connection_id) if config.source_connection_id else None,
        generation_method=config.generation_method.value,
        row_count=config.row_count,
        status=config.status,
        output_mode=output_mode,
        created_at=config.created_at.isoformat() if config.created_at else "",
    )


class OutputModeUpdate(BaseModel):
    output_mode: str


@router.patch("/configs/{config_id}/output-mode", response_model=ConfigResponse)
async def update_output_mode(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    body: OutputModeUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Update only the output_mode of a synthetic config."""
    if body.output_mode not in ALLOWED_OUTPUT_MODES:
        raise HTTPException(
            400,
            {
                "error": "invalid_output_mode",
                "detail": f"output_mode must be one of {sorted(ALLOWED_OUTPUT_MODES)}",
            },
        )
    from sqlalchemy import select as _select
    from app.infrastructure.persistence.models.synthetic import SyntheticConfigModel

    res = await session.execute(
        _select(SyntheticConfigModel).where(
            SyntheticConfigModel.id == config_id,
            SyntheticConfigModel.project_id == project_id,
        )
    )
    model = res.scalar_one_or_none()
    if model is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Config not found"})

    model.output_mode = body.output_mode
    await session.flush()

    return ConfigResponse(
        id=str(model.id),
        name=model.name,
        source_connection_id=str(model.source_connection_id) if model.source_connection_id else None,
        generation_method=model.generation_method,
        row_count=model.row_count,
        status=model.status,
        output_mode=model.output_mode,
        created_at=model.created_at.isoformat() if model.created_at else "",
    )


@router.get("/configs")
async def list_configs(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = SQLAlchemySyntheticRepository(session)
    handler = ListConfigsHandler(repo)
    configs = await handler.handle(ListConfigsQuery(project_id=project_id))

    # Side-lookup output_mode from the model since the domain entity doesn't
    # yet carry it (Phase 54 added the column without widening the entity).
    from sqlalchemy import select as _select
    from app.infrastructure.persistence.models.synthetic import SyntheticConfigModel
    if configs:
        ids = [c.id for c in configs]
        modes_q = await session.execute(
            _select(SyntheticConfigModel.id, SyntheticConfigModel.output_mode).where(
                SyntheticConfigModel.id.in_(ids)
            )
        )
        output_modes = {row[0]: row[1] for row in modes_q.all()}
    else:
        output_modes = {}

    return {
        "configs": [
            ConfigResponse(
                id=str(c.id), name=c.name,
                source_connection_id=str(c.source_connection_id) if c.source_connection_id else None,
                generation_method=c.generation_method.value, row_count=c.row_count,
                status=c.status,
                output_mode=output_modes.get(c.id, "same_database"),
                created_at=c.created_at.isoformat() if c.created_at else "",
            ).model_dump()
            for c in configs
        ]
    }


@router.get("/configs/{config_id}", response_model=ConfigResponse)
async def get_config(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = SQLAlchemySyntheticRepository(session)
    handler = GetConfigHandler(repo)
    try:
        config = await handler.handle(GetConfigQuery(config_id=config_id))
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Config not found"})

    # Side-lookup output_mode from the model.
    from sqlalchemy import select as _select
    from app.infrastructure.persistence.models.synthetic import SyntheticConfigModel
    mode_row = await session.execute(
        _select(SyntheticConfigModel.output_mode).where(SyntheticConfigModel.id == config.id)
    )
    output_mode = mode_row.scalar_one_or_none() or "same_database"

    return ConfigResponse(
        id=str(config.id), name=config.name,
        source_connection_id=str(config.source_connection_id) if config.source_connection_id else None,
        generation_method=config.generation_method.value, row_count=config.row_count,
        status=config.status,
        output_mode=output_mode,
        created_at=config.created_at.isoformat() if config.created_at else "",
    )


@router.post("/preview")
async def preview(
    project_id: uuid.UUID,
    body: PreviewRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Preview 10 rows synchronously (10-second timeout)."""
    repo = SQLAlchemySyntheticRepository(session)
    handler = PreviewHandler(repo)
    try:
        result = await handler.handle(PreviewCommand(config_id=uuid.UUID(body.config_id), limit=body.limit))
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Config not found"})
    except TimeoutError:
        raise HTTPException(status_code=504, detail={"error": "timeout", "detail": "Preview exceeded 10-second timeout"})
    return {"preview": result}


@router.post("/generate", response_model=GenerateResponse, status_code=202)
async def generate(
    project_id: uuid.UUID,
    body: GenerateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Dispatch async generation (returns job_id)."""
    repo = SQLAlchemySyntheticRepository(session)
    handler = GenerateHandler(repo, session)

    try:
        job_id = await handler.handle(
            GenerateCommand(
                config_id=uuid.UUID(body.config_id),
                project_id=project_id,
                user_id=uuid.UUID(current_user["id"]),
            )
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Config not found"})

    await logger.ainfo(
        "synthetic_generation_triggered",
        config_id=body.config_id,
        project_id=str(project_id),
        job_id=str(job_id),
        user_id=current_user["id"],
        ip=request.client.host if request.client else "unknown",
    )

    return GenerateResponse(job_id=str(job_id))


# --- NLP Generation ---


class NLPGenerateRequest(BaseModel):
    prompt: str
    connection_id: str


class NLPExecuteRequest(BaseModel):
    plan: dict
    connection_id: str
    name: str = "NLP Generation"
    row_count: int = 1000


@router.post("/nlp-generate")
async def nlp_generate_plan(
    project_id: uuid.UUID,
    body: NLPGenerateRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Generate a structured plan from NLP prompt (synchronous, 30s timeout)."""
    import asyncio
    from app.infrastructure.ai.llm_provider import create_provider
    from app.infrastructure.engine.llm_engine import LLMEngine
    from app.config import settings

    provider = create_provider(settings)
    if not provider:
        raise HTTPException(503, {"error": "llm_unavailable", "detail": "No LLM provider configured"})

    engine = LLMEngine(provider)

    try:
        async with asyncio.timeout(30):
            plan = await engine.create_plan(body.prompt, {"tables": []})
    except TimeoutError:
        raise HTTPException(504, {"error": "timeout", "detail": "Plan generation exceeded 30s"})

    await logger.ainfo("nlp_plan_generated", project_id=str(project_id), user_id=current_user["id"])
    return {"plan": plan}


@router.post("/nlp-execute", response_model=GenerateResponse, status_code=202)
async def nlp_execute(
    project_id: uuid.UUID,
    body: NLPExecuteRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    """Execute an NLP-generated plan (async via Celery)."""
    repo = SQLAlchemySyntheticRepository(session)

    config = await repo.save(
        __import__("app.domain.synthetic.entities", fromlist=["SyntheticConfig"]).SyntheticConfig(
            project_id=project_id,
            name=body.name,
            source_connection_id=uuid.UUID(body.connection_id),
            generation_method=__import__("app.domain.synthetic.value_objects", fromlist=["GenerationMethod"]).GenerationMethod.LLM,
            config={"plan": body.plan},
            row_count=body.row_count,
            status="pending",
        )
    )

    handler = GenerateHandler(repo, session)
    from app.application.synthetic.commands import GenerateCommand
    job_id = await handler.handle(GenerateCommand(
        config_id=config.id, project_id=project_id, user_id=uuid.UUID(current_user["id"]),
    ))

    await logger.ainfo("nlp_execution_triggered", config_id=str(config.id), job_id=str(job_id), user_id=current_user["id"])
    return GenerateResponse(job_id=str(job_id))


# Quality evaluation lives in ``synthetic_quality.py`` (split in Phase 61).
# File-schema and file-set endpoints live in ``synthetic_file_schemas.py``.
