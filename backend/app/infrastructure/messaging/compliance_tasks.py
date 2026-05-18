"""Compliance Celery tasks.

Phase 57 F2: moves regulation-report generation off the request thread. The
HTTP endpoint creates a JobModel row and dispatches ``run_report_generation``;
this task drives the existing ``GenerateReportHandler`` through the same
``pending → running → completed/failed`` lifecycle the rest of the job plane
uses, so the SSE stream + jobs API can surface progress without a special
case.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from app.infrastructure.messaging.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    acks_late=True,
)
def run_report_generation(
    self,
    job_id: str,
    project_id: str,
    regulation: str,
    user_id: str,
) -> None:
    """Generate a compliance report on the Celery worker pool.

    All real work happens in ``_run_report_generation_async`` — this thin
    sync wrapper exists only so Celery has a top-level function reference.
    """
    import asyncio

    asyncio.run(
        _run_report_generation_async(self, job_id, project_id, regulation, user_id)
    )


async def _run_report_generation_async(
    task,
    job_id: str,
    project_id: str,
    regulation: str,
    user_id: str,
) -> None:
    from sqlalchemy import update

    from app.application.compliance.commands import GenerateReportCommand
    from app.application.compliance.handlers import GenerateReportHandler
    from app.infrastructure.persistence.database import async_session_factory
    from app.infrastructure.persistence.models.job import JobModel
    from app.infrastructure.persistence.sqlalchemy.compliance_repo import (
        ComplianceRepository,
    )
    from app.infrastructure.persistence.sqlalchemy.connection_repo import (
        SQLAlchemyConnectionRepository,
    )
    from app.infrastructure.persistence.sqlalchemy.discovery_repo import (
        SQLAlchemyDiscoveryRepository,
    )
    from app.infrastructure.persistence.sqlalchemy.masking_repo import (
        SQLAlchemyMaskingRepository,
    )
    from app.container import Container
    from app.infrastructure.messaging.progress_pubsub import publish_progress

    job_uuid = uuid.UUID(job_id)
    project_uuid = uuid.UUID(project_id)
    user_uuid = uuid.UUID(user_id)

    # Stamp the Celery task id early so /jobs surfaces the linkage even if
    # the rest of the run blows up.
    async with async_session_factory() as session:
        try:
            await session.execute(
                update(JobModel)
                .where(JobModel.id == job_uuid)
                .values(
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    celery_task_id=task.request.id,
                    progress=10,
                )
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 10,
                "result_summary": None,
            })

            compliance_repo = ComplianceRepository(session)
            discovery_repo = SQLAlchemyDiscoveryRepository(session)
            masking_repo = SQLAlchemyMaskingRepository(session)
            connection_repo = SQLAlchemyConnectionRepository(session)
            storage = Container().storage_backend()

            handler = GenerateReportHandler(
                compliance_repo=compliance_repo,
                discovery_repo=discovery_repo,
                masking_repo=masking_repo,
                storage=storage,
                connection_repo=connection_repo,
            )

            await session.execute(
                update(JobModel).where(JobModel.id == job_uuid).values(progress=40)
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "running",
                "progress": 40,
                "result_summary": None,
            })

            report = await handler.handle(
                GenerateReportCommand(
                    project_id=project_uuid,
                    regulation=regulation,
                    user_id=user_uuid,
                )
            )

            # Make handler's flushes durable, then mark the job complete.
            compliance_result_summary = {
                "report_id": str(report.id),
                "storage_path": report.storage_path,
                "regulation": regulation,
            }
            await session.execute(
                update(JobModel)
                .where(JobModel.id == job_uuid)
                .values(
                    status="completed",
                    progress=100,
                    completed_at=datetime.now(timezone.utc),
                    result_summary=compliance_result_summary,
                )
            )
            await session.commit()
            publish_progress(str(job_uuid), {
                "status": "completed",
                "progress": 100,
                "result_summary": compliance_result_summary,
            })

            await logger.ainfo(
                "compliance_task_completed",
                job_id=job_id,
                project_id=project_id,
                regulation=regulation,
                report_id=str(report.id),
            )

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(
                project_id,
                "job.completed",
                {
                    "job_id": job_id,
                    "job_type": "compliance",
                    "regulation": regulation,
                    "report_id": str(report.id),
                },
            )

        except Exception as exc:
            await session.rollback()
            async with async_session_factory() as err_session:
                await err_session.execute(
                    update(JobModel)
                    .where(JobModel.id == job_uuid)
                    .values(
                        status="failed",
                        error_message=str(exc)[:1000],
                        completed_at=datetime.now(timezone.utc),
                    )
                )
                await err_session.commit()
            publish_progress(str(job_uuid), {
                "status": "failed",
                "progress": 0,
                "result_summary": None,
            })
            await logger.aerror(
                "compliance_task_failed",
                job_id=job_id,
                project_id=project_id,
                regulation=regulation,
                error=str(exc),
            )

            from app.infrastructure.messaging.celery_app import fire_webhooks
            await fire_webhooks(
                project_id,
                "job.failed",
                {
                    "job_id": job_id,
                    "job_type": "compliance",
                    "regulation": regulation,
                    "error": str(exc)[:500],
                },
            )
            # Re-raise so Celery's autoretry kicks in.
            raise
