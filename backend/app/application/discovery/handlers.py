"""Discovery command and query handlers."""

from __future__ import annotations

import uuid

import structlog

from app.domain.discovery.repository import DiscoveryRepository
from app.domain.discovery.value_objects import Classification, PIIType

from app.application.discovery.commands import (
    OverridePIIClassificationCommand,
    RunDiscoveryCommand,
)
from app.application.discovery.queries import (
    GetDiscoveryResultsQuery,
    GetPIIClassificationsQuery,
    GetRelationshipsQuery,
)

logger = structlog.get_logger()


class RunDiscoveryHandler:
    def __init__(self, discovery_repository, connection_repository, job_session):
        self._discovery_repo = discovery_repository
        self._connection_repo = connection_repository
        self._job_session = job_session

    async def handle(self, command: RunDiscoveryCommand) -> uuid.UUID:
        # Check no active discovery for this connection (concurrency limit)
        from app.infrastructure.persistence.models.job import JobModel
        from sqlalchemy import select

        result = await self._job_session.execute(
            select(JobModel).where(
                JobModel.reference_id == command.connection_id,
                JobModel.job_type == "discovery",
                JobModel.status.in_(["pending", "running"]),
            )
        )
        active_job = result.scalar_one_or_none()
        if active_job:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=409,
                detail={"error": "discovery_already_running", "detail": "A discovery is already running for this connection"},
            )

        # Create job record
        from app.infrastructure.persistence.models.job import JobModel
        job = JobModel(
            project_id=command.project_id,
            job_type="discovery",
            reference_id=command.connection_id,
            status="pending",
            progress=0,
            created_by=command.user_id,
        )
        self._job_session.add(job)
        await self._job_session.flush()

        # Dispatch Celery task
        from app.infrastructure.messaging.discovery_tasks import run_discovery_task
        run_discovery_task.delay(
            str(command.connection_id),
            str(command.project_id),
            str(job.id),
        )

        await logger.ainfo(
            "discovery_run_triggered",
            connection_id=str(command.connection_id),
            project_id=str(command.project_id),
            job_id=str(job.id),
            user_id=str(command.user_id),
        )

        return job.id


class OverridePIIHandler:
    def __init__(self, discovery_repository: DiscoveryRepository):
        self._repo = discovery_repository

    async def handle(self, command: OverridePIIClassificationCommand):
        column = await self._repo.update_column_classification(
            column_id=command.column_id,
            pii_type=PIIType(command.pii_type),
            classification=Classification.MANUALLY_CLASSIFIED,
            override_by=command.user_id,
            override_note=command.note,
        )

        await logger.ainfo(
            "pii_classification_overridden",
            column_id=str(command.column_id),
            pii_type=command.pii_type,
            user_id=str(command.user_id),
        )

        return column


class GetDiscoveryResultsHandler:
    def __init__(self, discovery_repository: DiscoveryRepository):
        self._repo = discovery_repository

    async def handle(self, query: GetDiscoveryResultsQuery):
        schemas = await self._repo.find_by_connection_id(query.connection_id)
        result = []
        for schema in schemas:
            tables = await self._repo.get_tables_by_schema_id(schema.id)
            table_data = []
            for table in tables:
                columns = await self._repo.get_columns_by_table_id(table.id)
                table_data.append({"table": table, "columns": columns})
            result.append({"schema": schema, "tables": table_data})
        return result


class GetPIIClassificationsHandler:
    def __init__(self, discovery_repository: DiscoveryRepository):
        self._repo = discovery_repository

    async def handle(self, query: GetPIIClassificationsQuery):
        columns = await self._repo.get_pii_columns(query.schema_id, query.min_confidence)

        if query.pii_type:
            columns = [c for c in columns if c.pii_type.value == query.pii_type]
        if query.classification:
            columns = [c for c in columns if c.classification.value == query.classification]

        return columns


class GetRelationshipsHandler:
    def __init__(self, discovery_repository: DiscoveryRepository):
        self._repo = discovery_repository

    async def handle(self, query: GetRelationshipsQuery):
        return await self._repo.get_relationships(query.schema_id)
