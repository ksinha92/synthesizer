"""Synthetic command and query handlers."""

from __future__ import annotations

import asyncio
import uuid

import structlog

from app.domain.shared.errors import NotFoundError
from app.domain.synthetic.entities import SyntheticConfig
from app.domain.synthetic.repository import SyntheticRepository
from app.domain.synthetic.value_objects import GenerationMethod
from app.infrastructure.engine.faker_engine import FakerEngine

from app.application.synthetic.commands import (
    CreateSyntheticConfigCommand,
    GenerateCommand,
    PreviewCommand,
)
from app.application.synthetic.queries import GetConfigQuery, ListConfigsQuery

logger = structlog.get_logger()

PREVIEW_TIMEOUT = 10.0  # seconds


class CreateConfigHandler:
    def __init__(self, repository: SyntheticRepository) -> None:
        self._repo = repository

    async def handle(self, command: CreateSyntheticConfigCommand) -> SyntheticConfig:
        config = SyntheticConfig(
            project_id=command.project_id,
            name=command.name,
            source_connection_id=command.source_connection_id,
            generation_method=GenerationMethod(command.generation_method),
            tables=command.tables,
            config=command.config,
            nlp_prompt=command.nlp_prompt,
            row_count=command.row_count,
            status="draft",
        )
        saved = await self._repo.save(config)
        await logger.ainfo("synthetic_config_created", config_id=str(saved.id), project_id=str(command.project_id))
        return saved


class PreviewHandler:
    def __init__(self, repository: SyntheticRepository) -> None:
        self._repo = repository

    async def handle(self, command: PreviewCommand) -> dict[str, list[dict]]:
        config = await self._repo.get(command.config_id)
        if config is None:
            raise NotFoundError(message=f"Config {command.config_id} not found")

        seed = config.config.get("seed")
        engine = FakerEngine(seed=seed)

        schema_metadata = {"relationships": []}  # Simplified for preview

        try:
            async with asyncio.timeout(PREVIEW_TIMEOUT):
                return await engine.preview(config, schema_metadata, limit=command.limit)
        except TimeoutError:
            raise TimeoutError("Preview generation exceeded 10-second timeout")


class GenerateHandler:
    def __init__(self, repository: SyntheticRepository, job_session) -> None:
        self._repo = repository
        self._job_session = job_session

    async def handle(self, command: GenerateCommand) -> uuid.UUID:
        config = await self._repo.get(command.config_id)
        if config is None:
            raise NotFoundError(message=f"Config {command.config_id} not found")

        # Create job record
        from app.infrastructure.persistence.models.job import JobModel
        job = JobModel(
            project_id=command.project_id,
            job_type="generation",
            reference_id=command.config_id,
            status="pending",
            progress=0,
            created_by=command.user_id,
        )
        self._job_session.add(job)
        await self._job_session.flush()

        # Dispatch Celery task
        from app.infrastructure.messaging.synthetic_tasks import run_generation_task
        run_generation_task.delay(str(command.config_id), str(command.project_id), str(job.id))

        await logger.ainfo(
            "synthetic_generation_triggered",
            config_id=str(command.config_id),
            job_id=str(job.id),
            user_id=str(command.user_id),
        )
        return job.id


class GetConfigHandler:
    def __init__(self, repository: SyntheticRepository) -> None:
        self._repo = repository

    async def handle(self, query: GetConfigQuery) -> SyntheticConfig:
        config = await self._repo.get(query.config_id)
        if config is None:
            raise NotFoundError(message=f"Config {query.config_id} not found")
        return config


class ListConfigsHandler:
    def __init__(self, repository: SyntheticRepository) -> None:
        self._repo = repository

    async def handle(self, query: ListConfigsQuery) -> list[SyntheticConfig]:
        return await self._repo.find_by_project_id(query.project_id)
