"""SQLAlchemy workflow repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.workflow.entities import Workflow
from app.infrastructure.persistence.models.workflow import WorkflowModel


class WorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, wf_id: uuid.UUID) -> Workflow | None:
        result = await self._session.execute(select(WorkflowModel).where(WorkflowModel.id == wf_id))
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def save(self, entity: Workflow) -> Workflow:
        result = await self._session.execute(select(WorkflowModel).where(WorkflowModel.id == entity.id))
        existing = result.scalar_one_or_none()
        if existing:
            existing.name = entity.name
            existing.description = entity.description
            existing.dag_definition = entity.dag_definition
            existing.is_active = entity.is_active
            await self._session.flush()
            return self._to_entity(existing)
        model = WorkflowModel(
            id=entity.id, project_id=entity.project_id, name=entity.name,
            description=entity.description, dag_definition=entity.dag_definition,
            is_active=entity.is_active,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def find_by_project_id(self, project_id: uuid.UUID) -> list[Workflow]:
        result = await self._session.execute(
            select(WorkflowModel).where(WorkflowModel.project_id == project_id).order_by(WorkflowModel.created_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(m: WorkflowModel) -> Workflow:
        return Workflow(
            id=m.id, project_id=m.project_id, name=m.name, description=m.description,
            dag_definition=m.dag_definition or {}, is_active=m.is_active,
            created_at=m.created_at, updated_at=m.updated_at,
        )
