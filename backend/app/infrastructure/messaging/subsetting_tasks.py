"""Subsetting Celery tasks."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, retry_backoff=True, retry_backoff_max=120, acks_late=True)
def run_subsetting_task(self, config_id: str, project_id: str, job_id: str):
    import asyncio
    asyncio.run(_run_async(self, config_id, project_id, job_id))


async def _run_async(task, config_id, project_id, job_id):
    import uuid
    from sqlalchemy import select, update

    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.job import JobModel
    from app.infrastructure.persistence.models.connection import ConnectionModel
    from app.infrastructure.persistence.sqlalchemy.subsetting_repo import SubsettingRepository
    from app.infrastructure.persistence.sqlalchemy.discovery_repo import SQLAlchemyDiscoveryRepository
    from app.infrastructure.connectors.registry import create_registry
    from app.infrastructure.engine.subsetting_engine import SubsettingEngine
    from app.infrastructure.messaging.progress_pubsub import publish_progress
    from app.domain.connection.value_objects import ConnectorType
    from app.infrastructure.persistence.sqlalchemy.connection_repo import _decrypt_credentials

    config_uuid = uuid.UUID(config_id)
    job_uuid = uuid.UUID(job_id)

    async with async_session_factory() as session:
        try:
            # F9: stamp celery_task_id so cancel-by-Celery-ID becomes possible.
            job = await session.get(JobModel, job_uuid)
            if job and not job.celery_task_id:
                job.celery_task_id = task.request.id

            await session.execute(update(JobModel).where(JobModel.id == job_uuid).values(status="running", started_at=datetime.now(timezone.utc)))
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 0,
                "result_summary": None,
            })

            # Load subsetting config
            subset_repo = SubsettingRepository(session)
            config = await subset_repo.get(config_uuid)
            if not config:
                raise ValueError(f"Subset config {config_id} not found")
            if config.source_connection_id is None:
                raise ValueError(
                    f"Subset config {config_id} has no source connection — reassign one before re-running"
                )

            # Load source connection
            result = await session.execute(
                select(ConnectionModel).where(ConnectionModel.id == config.source_connection_id)
            )
            conn_model = result.scalar_one_or_none()
            if not conn_model:
                raise ValueError(f"Source connection {config.source_connection_id} not found")

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

            # Update progress: config loaded
            await session.execute(update(JobModel).where(JobModel.id == job_uuid).values(progress=10))
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 10,
                "result_summary": None,
            })

            # Load discovered relationships for this connection's schemas
            discovery_repo = SQLAlchemyDiscoveryRepository(session)
            schemas = await discovery_repo.find_by_connection_id(conn_model.id)

            relationships = []
            for schema in schemas:
                # Build table_id → table_name lookup
                tables = await discovery_repo.get_tables_by_schema_id(schema.id)
                table_name_map = {t.id: t.table_name for t in tables}

                rels = await discovery_repo.get_relationships(schema.id)
                for rel in rels:
                    source_name = table_name_map.get(rel.source_table_id, str(rel.source_table_id))
                    target_name = table_name_map.get(rel.target_table_id, str(rel.target_table_id))
                    relationships.append({
                        "source_table": source_name,
                        "target_table": target_name,
                    })

            # Update progress: relationships loaded
            await session.execute(update(JobModel).where(JobModel.id == job_uuid).values(progress=25))
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 25,
                "result_summary": None,
            })

            # Build FK graph and execute subset
            engine = SubsettingEngine()
            graph = engine.build_graph(relationships)

            # Update progress: graph built
            await session.execute(update(JobModel).where(JobModel.id == job_uuid).values(progress=40))
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 40,
                "result_summary": None,
            })

            # Initialize storage for persisting subset results via the DI container so
            # the local/s3 selection lives in one place (see app.container).
            from app.container import Container
            storage = Container().storage_backend()

            result_counts = await engine.execute_subset(connector, graph, config, storage=storage)

            await connector.close()

            # Mark complete
            total_rows = sum(result_counts.values())
            subset_result_summary = {"tables": len(result_counts), "total_rows": total_rows, "per_table": result_counts}
            await session.execute(update(JobModel).where(JobModel.id == job_uuid).values(
                status="completed", progress=100,
                completed_at=datetime.now(timezone.utc),
                result_summary=subset_result_summary,
            ))
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "completed",
                "progress": 100,
                "result_summary": subset_result_summary,
            })

            await logger.ainfo("subsetting_task_completed", config_id=config_id, job_id=job_id, tables=len(result_counts), rows=total_rows)

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.completed", {"job_id": job_id, "job_type": "subsetting", "tables": len(result_counts), "total_rows": total_rows})

        except Exception as exc:
            await session.rollback()
            async with async_session_factory() as err_session:
                await err_session.execute(update(JobModel).where(JobModel.id == job_uuid).values(status="failed", error_message=str(exc)[:1000]))
                await err_session.commit()
            publish_progress(str(job_uuid), {
                "status": "failed",
                "progress": 0,
                "result_summary": None,
            })
            await logger.aerror("subsetting_task_failed", config_id=config_id, job_id=job_id, error=str(exc))

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(project_id, "job.failed", {"job_id": job_id, "job_type": "subsetting", "error": str(exc)[:500]})

            raise task.retry(exc=exc)
