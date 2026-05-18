"""Audit log repository."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.audit import AuditLogModel


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(self, user_id: uuid.UUID | None, project_id: uuid.UUID | None, action: str, resource_type: str | None = None, resource_id: uuid.UUID | None = None, details: dict | None = None, ip_address: str | None = None, status_code: int | None = None) -> None:
        # Sanitize details — strip sensitive fields
        safe_details = self._sanitize_details(details) if details else None

        entry = AuditLogModel(
            user_id=user_id, project_id=project_id, action=action,
            resource_type=resource_type, resource_id=resource_id,
            details=safe_details, ip_address=ip_address, status_code=status_code,
            created_at=datetime.now(__import__("datetime").timezone.utc),
        )
        self._session.add(entry)
        await self._session.flush()

    async def list_logs(self, project_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None, action: str | None = None, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        query = select(AuditLogModel)
        count_query = select(func.count()).select_from(AuditLogModel)

        if project_id:
            query = query.where(AuditLogModel.project_id == project_id)
            count_query = count_query.where(AuditLogModel.project_id == project_id)
        if user_id:
            query = query.where(AuditLogModel.user_id == user_id)
            count_query = count_query.where(AuditLogModel.user_id == user_id)
        if action:
            query = query.where(AuditLogModel.action.contains(action))
            count_query = count_query.where(AuditLogModel.action.contains(action))

        query = query.order_by(AuditLogModel.created_at.desc()).limit(page_size).offset((page - 1) * page_size)

        result = await self._session.execute(query)
        count_result = await self._session.execute(count_query)

        logs = [
            {"id": str(m.id), "user_id": str(m.user_id) if m.user_id else None, "project_id": str(m.project_id) if m.project_id else None, "action": m.action, "resource_type": m.resource_type, "details": m.details, "ip_address": m.ip_address, "status_code": m.status_code, "created_at": m.created_at.isoformat()}
            for m in result.scalars().all()
        ]
        return logs, count_result.scalar_one()

    @staticmethod
    def _sanitize_details(details: dict) -> dict:
        """Remove sensitive fields from audit log details."""
        sensitive_keys = {"password", "credentials", "secret", "api_key", "token", "client_secret"}
        return {k: "***" if k.lower() in sensitive_keys else v for k, v in details.items()}
