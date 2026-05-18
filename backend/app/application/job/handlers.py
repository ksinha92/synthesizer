"""Job handlers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from app.domain.shared.errors import NotFoundError
from app.domain.shared.job import Job, JobStatus
from app.infrastructure.persistence.sqlalchemy.job_repo import JobRepository

logger = structlog.get_logger()


class ListJobsHandler:
    def __init__(self, repo: JobRepository):
        self._repo = repo

    async def handle(self, project_id: uuid.UUID, page=1, page_size=20, job_type=None, status=None):
        return await self._repo.list_by_project(project_id, page, page_size, job_type, status)


class GetJobHandler:
    def __init__(self, repo: JobRepository):
        self._repo = repo

    async def handle(self, job_id: uuid.UUID) -> Job:
        job = await self._repo.get(job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        return job


class CancelJobHandler:
    def __init__(self, repo: JobRepository):
        self._repo = repo

    async def handle(self, job_id: uuid.UUID, project_id: uuid.UUID) -> Job:
        job = await self._repo.get(job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        if job.project_id != project_id:
            raise NotFoundError(f"Job {job_id} not found in project")

        if job.celery_task_id:
            try:
                from app.infrastructure.messaging.celery_app import celery_app
                celery_app.control.revoke(job.celery_task_id, terminate=True)
            except Exception as e:
                await logger.awarning("celery_revoke_failed", job_id=str(job_id), error=str(e))

        job.status = JobStatus.CANCELLED
        job.cancelled_at = datetime.now(timezone.utc)
        saved = await self._repo.save(job)
        await logger.ainfo("job_cancelled", job_id=str(job_id))
        return saved


class RetryJobHandler:
    def __init__(self, repo: JobRepository):
        self._repo = repo

    async def handle(self, job_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
        job = await self._repo.get(job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        if job.project_id != project_id:
            raise NotFoundError(f"Job {job_id} not found in project")
        if not job.can_retry():
            raise ValueError("Job cannot be retried (not failed or cancelled)")

        new_job = Job(
            project_id=job.project_id,
            job_type=job.job_type,
            reference_id=job.reference_id,
            status=JobStatus.PENDING,
            created_by=user_id,
        )
        saved = await self._repo.save(new_job)

        # Re-dispatch Celery task
        if job.job_type.value == "discovery":
            from app.infrastructure.messaging.discovery_tasks import run_discovery_task
            run_discovery_task.delay(str(job.reference_id), str(job.project_id), str(saved.id))
        elif job.job_type.value == "generation":
            from app.infrastructure.messaging.synthetic_tasks import run_generation_task
            run_generation_task.delay(str(job.reference_id), str(job.project_id), str(saved.id))

        await logger.ainfo("job_retried", original_job_id=str(job_id), new_job_id=str(saved.id))
        return saved.id
