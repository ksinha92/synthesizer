"""SQLAlchemy implementation of SyntheticRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.synthetic.entities import SyntheticConfig
from app.domain.synthetic.repository import SyntheticRepository
from app.domain.synthetic.value_objects import GenerationMethod
from app.infrastructure.persistence.models.synthetic import SyntheticConfigModel


class SQLAlchemySyntheticRepository(SyntheticRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: uuid.UUID) -> SyntheticConfig | None:
        result = await self._session.execute(
            select(SyntheticConfigModel).where(SyntheticConfigModel.id == entity_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, entity: SyntheticConfig) -> SyntheticConfig:
        result = await self._session.execute(
            select(SyntheticConfigModel).where(SyntheticConfigModel.id == entity.id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = entity.name
            existing.tables = entity.tables
            existing.generation_method = entity.generation_method.value
            existing.config = entity.config
            existing.nlp_prompt = entity.nlp_prompt
            existing.row_count = entity.row_count
            existing.status = entity.status
            await self._session.flush()
            return self._to_entity(existing)
        else:
            model = SyntheticConfigModel(
                id=entity.id,
                project_id=entity.project_id,
                name=entity.name,
                source_connection_id=entity.source_connection_id,
                target_connection_id=entity.target_connection_id,
                tables=entity.tables,
                generation_method=entity.generation_method.value,
                config=entity.config,
                nlp_prompt=entity.nlp_prompt,
                row_count=entity.row_count,
                status=entity.status,
            )
            self._session.add(model)
            await self._session.flush()
            return self._to_entity(model)

    async def delete(self, entity_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(SyntheticConfigModel).where(SyntheticConfigModel.id == entity_id)
        )

    async def list(self, limit: int = 100, offset: int = 0) -> list[SyntheticConfig]:
        result = await self._session.execute(
            select(SyntheticConfigModel).limit(limit).offset(offset)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_project_id(self, project_id: uuid.UUID) -> list[SyntheticConfig]:
        result = await self._session.execute(
            select(SyntheticConfigModel)
            .where(SyntheticConfigModel.project_id == project_id)
            .order_by(SyntheticConfigModel.created_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(model: SyntheticConfigModel) -> SyntheticConfig:
        return SyntheticConfig(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            source_connection_id=model.source_connection_id,
            target_connection_id=model.target_connection_id,
            tables=model.tables or [],
            generation_method=GenerationMethod(model.generation_method),
            config=model.config or {},
            nlp_prompt=model.nlp_prompt,
            row_count=model.row_count,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
