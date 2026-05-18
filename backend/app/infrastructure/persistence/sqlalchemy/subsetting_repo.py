"""SQLAlchemy subsetting repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.subsetting.entities import SubsetConfig
from app.infrastructure.persistence.models.subsetting import SubsetConfigModel


class SubsettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, config_id: uuid.UUID) -> SubsetConfig | None:
        result = await self._session.execute(select(SubsetConfigModel).where(SubsetConfigModel.id == config_id))
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def save(self, entity: SubsetConfig) -> SubsetConfig:
        model = SubsetConfigModel(
            id=entity.id, project_id=entity.project_id, name=entity.name,
            source_connection_id=entity.source_connection_id, target_connection_id=entity.target_connection_id,
            target_percentage=entity.target_percentage, target_row_count=entity.target_row_count,
            root_tables=entity.root_tables, traversal_strategy=entity.traversal_strategy,
            output_mode=entity.output_mode,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def find_by_project_id(self, project_id: uuid.UUID) -> list[SubsetConfig]:
        result = await self._session.execute(
            select(SubsetConfigModel).where(SubsetConfigModel.project_id == project_id).order_by(SubsetConfigModel.created_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(m: SubsetConfigModel) -> SubsetConfig:
        return SubsetConfig(
            id=m.id, project_id=m.project_id, name=m.name,
            source_connection_id=m.source_connection_id, target_connection_id=m.target_connection_id,
            target_percentage=m.target_percentage, target_row_count=m.target_row_count,
            root_tables=m.root_tables or [], traversal_strategy=m.traversal_strategy,
            output_mode=m.output_mode,
            created_at=m.created_at, updated_at=m.updated_at,
        )
