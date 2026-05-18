"""Subsetting handlers."""

from __future__ import annotations

import uuid

import structlog

from app.domain.subsetting.entities import SubsetConfig
from app.domain.shared.errors import NotFoundError
from app.infrastructure.engine.subsetting_engine import SubsettingEngine

from app.application.subsetting.commands import *

logger = structlog.get_logger()


class CreateConfigHandler:
    def __init__(self, repo):
        self._repo = repo

    async def handle(self, cmd: CreateSubsetConfigCommand) -> SubsetConfig:
        config = SubsetConfig(
            project_id=cmd.project_id, name=cmd.name,
            source_connection_id=cmd.source_connection_id,
            target_percentage=cmd.target_percentage, target_row_count=cmd.target_row_count,
            root_tables=cmd.root_tables, traversal_strategy=cmd.traversal_strategy,
            output_mode=cmd.output_mode,
        )
        return await self._repo.save(config)


class AnalyzeHandler:
    """Dry-run subset analyzer.

    Loads the source connection + discovered relationships, builds the FK graph,
    and asks the engine to estimate row counts per table without extracting data.
    """

    def __init__(self, repo, session):
        self._repo = repo
        self._session = session

    async def handle(self, cmd: AnalyzeSubsetCommand) -> list[dict]:
        from sqlalchemy import select

        from app.domain.connection.value_objects import ConnectorType
        from app.infrastructure.connectors.registry import create_registry
        from app.infrastructure.persistence.models.connection import ConnectionModel
        from app.infrastructure.persistence.sqlalchemy.connection_repo import (
            _decrypt_credentials,
        )
        from app.infrastructure.persistence.sqlalchemy.discovery_repo import (
            SQLAlchemyDiscoveryRepository,
        )

        config = await self._repo.get(cmd.config_id)
        if not config:
            raise NotFoundError(f"Subset config {cmd.config_id} not found")

        if config.source_connection_id is None:
            raise NotFoundError(
                f"Subset config {cmd.config_id} has no source connection — "
                "reassign one before analyzing"
            )

        # Load source connection
        result = await self._session.execute(
            select(ConnectionModel).where(ConnectionModel.id == config.source_connection_id)
        )
        conn_model = result.scalar_one_or_none()
        if not conn_model:
            raise NotFoundError(
                f"Source connection {config.source_connection_id} not found"
            )

        creds = _decrypt_credentials(conn_model.credentials or {})
        registry = create_registry()
        connector = registry.get_connector(
            connector_type=ConnectorType(conn_model.connector_type),
            host=conn_model.host,
            port=conn_model.port,
            database_name=conn_model.database_name,
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            extra_params=conn_model.extra_params,
        )

        try:
            # Load discovered relationships for this connection
            discovery_repo = SQLAlchemyDiscoveryRepository(self._session)
            schemas = await discovery_repo.find_by_connection_id(conn_model.id)

            relationships: list[dict] = []
            for schema in schemas:
                tables = await discovery_repo.get_tables_by_schema_id(schema.id)
                table_name_map = {t.id: t.table_name for t in tables}
                rels = await discovery_repo.get_relationships(schema.id)
                for rel in rels:
                    source_name = table_name_map.get(
                        rel.source_table_id, str(rel.source_table_id)
                    )
                    target_name = table_name_map.get(
                        rel.target_table_id, str(rel.target_table_id)
                    )
                    relationships.append(
                        {"source_table": source_name, "target_table": target_name}
                    )

            engine = SubsettingEngine()
            graph = engine.build_graph(relationships)
            return await engine.analyze_dry_run(connector, graph, config)
        finally:
            await connector.close()


class ExecuteHandler:
    def __init__(self, repo, job_session):
        self._repo = repo
        self._session = job_session

    async def handle(self, cmd: ExecuteSubsetCommand) -> uuid.UUID:
        config = await self._repo.get(cmd.config_id)
        if not config:
            raise NotFoundError(f"Subset config {cmd.config_id} not found")

        from app.infrastructure.persistence.models.job import JobModel
        job = JobModel(project_id=cmd.project_id, job_type="subsetting", reference_id=cmd.config_id, status="pending", created_by=cmd.user_id)
        self._session.add(job)
        await self._session.flush()

        from app.infrastructure.messaging.subsetting_tasks import run_subsetting_task
        run_subsetting_task.delay(str(cmd.config_id), str(cmd.project_id), str(job.id))

        await logger.ainfo("subset_execution_triggered", config_id=str(cmd.config_id), job_id=str(job.id))
        return job.id
