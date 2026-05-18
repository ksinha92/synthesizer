"""SQLAlchemy Job repository."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.job import Job, JobStatus, JobType
from app.infrastructure.persistence.models.job import JobModel


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, job_id: uuid.UUID) -> Job | None:
        result = await self._session.execute(select(JobModel).where(JobModel.id == job_id))
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, job: Job) -> Job:
        result = await self._session.execute(select(JobModel).where(JobModel.id == job.id))
        existing = result.scalar_one_or_none()
        if existing:
            for attr in ("status", "progress", "error_message", "started_at", "completed_at", "cancelled_at", "checkpoint", "celery_task_id", "result_summary"):
                setattr(existing, attr, getattr(job, attr, None) if hasattr(job, attr) else getattr(existing, attr))
            await self._session.flush()
            return self._to_entity(existing)
        model = JobModel(
            id=job.id, project_id=job.project_id, job_type=job.job_type.value,
            reference_id=job.reference_id, status=job.status.value, progress=job.progress,
            error_message=job.error_message, created_by=job.created_by,
            started_at=job.started_at, completed_at=job.completed_at,
            cancelled_at=job.cancelled_at, checkpoint=job.checkpoint,
            celery_task_id=job.celery_task_id, result_summary=job.result_summary,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def list_by_project(
        self, project_id: uuid.UUID, page: int = 1, page_size: int = 20,
        job_type: str | None = None, status: str | None = None,
    ) -> tuple[list[Job], int]:
        query = select(JobModel).where(JobModel.project_id == project_id)
        count_query = select(func.count()).select_from(JobModel).where(JobModel.project_id == project_id)

        if job_type:
            query = query.where(JobModel.job_type == job_type)
            count_query = count_query.where(JobModel.job_type == job_type)
        if status:
            query = query.where(JobModel.status == status)
            count_query = count_query.where(JobModel.status == status)

        query = query.order_by(JobModel.created_at.desc()).limit(page_size).offset((page - 1) * page_size)

        result = await self._session.execute(query)
        count_result = await self._session.execute(count_query)

        return [self._to_entity(m) for m in result.scalars().all()], count_result.scalar_one()

    async def update_progress(self, job_id: uuid.UUID, progress: int, message: str | None = None) -> None:
        values = {"progress": progress}
        if message:
            values["checkpoint"] = {"message": message}
        await self._session.execute(update(JobModel).where(JobModel.id == job_id).values(**values))

    @staticmethod
    def _to_entity(m: JobModel) -> Job:
        return Job(
            id=m.id, project_id=m.project_id, job_type=JobType(m.job_type),
            reference_id=m.reference_id, status=JobStatus(m.status), progress=m.progress,
            error_message=m.error_message, created_by=m.created_by,
            started_at=m.started_at, completed_at=m.completed_at,
            cancelled_at=m.cancelled_at, checkpoint=m.checkpoint,
            celery_task_id=m.celery_task_id, result_summary=m.result_summary,
            created_at=m.created_at, updated_at=m.updated_at,
        )
