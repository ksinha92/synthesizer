"""SQLAlchemy compliance repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.compliance.entities import ComplianceReport
from app.infrastructure.persistence.models.compliance import ComplianceReportModel


class ComplianceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entity: ComplianceReport) -> ComplianceReport:
        model = ComplianceReportModel(
            id=entity.id, project_id=entity.project_id, report_type=entity.report_type,
            generated_at=entity.generated_at, summary=entity.summary,
            storage_path=entity.storage_path, created_by=entity.created_by,
            legacy=entity.legacy,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def find_by_project_id(self, project_id: uuid.UUID) -> list[ComplianceReport]:
        result = await self._session.execute(
            select(ComplianceReportModel).where(ComplianceReportModel.project_id == project_id)
            .order_by(ComplianceReportModel.generated_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get(self, report_id: uuid.UUID) -> ComplianceReport | None:
        result = await self._session.execute(select(ComplianceReportModel).where(ComplianceReportModel.id == report_id))
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    @staticmethod
    def _to_entity(m: ComplianceReportModel) -> ComplianceReport:
        return ComplianceReport(
            id=m.id, project_id=m.project_id, report_type=m.report_type,
            generated_at=m.generated_at, summary=m.summary or {},
            storage_path=m.storage_path, created_by=m.created_by,
            legacy=bool(getattr(m, "legacy", False)),
            created_at=m.created_at, updated_at=m.updated_at,
        )
