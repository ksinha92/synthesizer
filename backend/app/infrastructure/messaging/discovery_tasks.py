"""Discovery Celery tasks."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=120,
    acks_late=True,
)
def run_discovery_task(self, connection_id: str, project_id: str, job_id: str):
    """Run schema discovery + PII detection as async Celery task.

    Retry policy: 3 retries with exponential backoff (30s, 60s, 120s).
    """
    import asyncio

    asyncio.run(_run_discovery_async(self, connection_id, project_id, job_id))


async def _run_discovery_async(task, connection_id: str, project_id: str, job_id: str):
    """Async inner function for discovery execution."""
    import uuid

    from sqlalchemy import select, update

    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.job import JobModel
    from app.infrastructure.persistence.models.connection import ConnectionModel
    from app.infrastructure.persistence.sqlalchemy.discovery_repo import SQLAlchemyDiscoveryRepository
    from app.infrastructure.connectors.registry import create_registry
    from app.infrastructure.ai.pii_detector import PIIDetectionService
    from app.infrastructure.messaging.progress_pubsub import publish_progress
    from app.domain.discovery.services import SchemaDiscoveryService
    from app.domain.connection.value_objects import ConnectorType, ConnectionCredentials

    conn_uuid = uuid.UUID(connection_id)
    job_uuid = uuid.UUID(job_id)

    async with async_session_factory() as session:
        try:
            # F9: stamp celery_task_id so cancel-by-Celery-ID becomes possible.
            job = await session.get(JobModel, job_uuid)
            if job and not job.celery_task_id:
                job.celery_task_id = task.request.id

            # Update job to running
            await session.execute(
                update(JobModel)
                .where(JobModel.id == job_uuid)
                .values(status="running", started_at=datetime.now(timezone.utc))
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": job.progress if job else 0,
                "result_summary": None,
            })

            # Load connection
            result = await session.execute(
                select(ConnectionModel).where(ConnectionModel.id == conn_uuid)
            )
            conn_model = result.scalar_one_or_none()
            if not conn_model:
                raise ValueError(f"Connection {connection_id} not found")

            # Create a minimal connection object for the service
            class _ConnProxy:
                def __init__(self, m):
                    self.id = m.id
                    self.connector_type = ConnectorType(m.connector_type)
                    self.host = m.host
                    self.port = m.port
                    self.database_name = m.database_name
                    creds = m.credentials or {}
                    self.credentials = ConnectionCredentials(
                        username=creds.get("username", ""),
                        password=creds.get("password", ""),
                    )
                    self.extra_params = m.extra_params or {}

            connection = _ConnProxy(conn_model)
            registry = create_registry()
            discovery_repo = SQLAlchemyDiscoveryRepository(session)

            # Load enabled sensitivity rules once. value_regex rules run inside
            # the discovery service against RAW samples (before masking);
            # column-name rules run later in the detector as Layer 0.
            from sqlalchemy import select as _select
            from app.infrastructure.persistence.models.sensitivity_rule import (
                SensitivityRuleModel,
            )

            rules_query = (
                _select(SensitivityRuleModel)
                .where(SensitivityRuleModel.enabled == True)  # noqa: E712
                .order_by(SensitivityRuleModel.priority, SensitivityRuleModel.name)
            )
            rules_rows = (await session.execute(rules_query)).scalars().all()
            custom_rules = [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "match_type": r.match_type,
                    "pattern": r.pattern,
                    "suggested_pii_type": r.suggested_pii_type,
                    "priority": r.priority,
                    "enabled": r.enabled,
                }
                for r in rules_rows
            ]

            # Run discovery — value_regex rules evaluated here, on raw samples.
            service = SchemaDiscoveryService(registry, discovery_repo)
            schema = await service.discover(connection, custom_rules=custom_rules)

            # Run PII detection — column-name rules evaluated here.
            pii_service = PIIDetectionService()
            tables = await discovery_repo.get_tables_by_schema_id(schema.id)
            for table in tables:
                columns = await discovery_repo.get_columns_by_table_id(table.id)
                await pii_service.detect(columns, custom_rules=custom_rules)
                # Persist PII results
                for col in columns:
                    await discovery_repo.update_column_classification(
                        column_id=col.id,
                        pii_type=col.pii_type,
                        classification=col.classification,
                    )

            # Update job to completed
            await session.execute(
                update(JobModel)
                .where(JobModel.id == job_uuid)
                .values(status="completed", progress=100, completed_at=datetime.now(timezone.utc))
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "completed",
                "progress": 100,
                "result_summary": None,
            })

            await logger.ainfo(
                "discovery_task_completed",
                connection_id=connection_id,
                job_id=job_id,
            )

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.completed", {"job_id": job_id, "job_type": "discovery", "connection_id": connection_id})

        except Exception as exc:
            await session.rollback()

            # Update job to failed
            async with async_session_factory() as err_session:
                await err_session.execute(
                    update(JobModel)
                    .where(JobModel.id == job_uuid)
                    .values(status="failed", error_message=str(exc)[:1000])
                )
                await err_session.commit()
            publish_progress(str(job_uuid), {
                "status": "failed",
                "progress": 0,
                "result_summary": None,
            })

            await logger.aerror(
                "discovery_task_failed",
                connection_id=connection_id,
                job_id=job_id,
                error=str(exc),
                retry=task.request.retries,
            )

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.failed", {"job_id": job_id, "job_type": "discovery", "error": str(exc)[:500]})

            # Retry with exponential backoff
            raise task.retry(exc=exc)
