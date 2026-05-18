"""SQLAlchemy implementation of ConnectionRepository with Fernet encryption."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = structlog.get_logger()

from app.domain.connection.entities import Connection
from app.domain.connection.repository import ConnectionRepository
from app.domain.connection.value_objects import (
    ConnectionCredentials,
    ConnectionStatus,
    ConnectorType,
)
from app.infrastructure.persistence.models.connection import ConnectionModel


def _get_encryption():
    """Lazy init encryption — returns None if FERNET_KEY not set."""
    if not settings.FERNET_KEY:
        return None
    from app.infrastructure.security.encryption import CredentialEncryption
    return CredentialEncryption(settings.FERNET_KEY)


def _encrypt_credentials(creds_dict: dict) -> dict:
    enc = _get_encryption()
    if enc:
        return enc.encrypt(creds_dict)
    return creds_dict


def _decrypt_credentials(creds_data: dict) -> dict:
    enc = _get_encryption()
    if enc and "_encrypted" in creds_data:
        return enc.decrypt(creds_data)
    return creds_data


class SQLAlchemyConnectionRepository(ConnectionRepository):
    """SQLAlchemy-backed connection repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: uuid.UUID) -> Connection | None:
        result = await self._session.execute(
            select(ConnectionModel).where(ConnectionModel.id == entity_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def save(self, entity: Connection) -> Connection:
        result = await self._session.execute(
            select(ConnectionModel).where(ConnectionModel.id == entity.id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = entity.name
            existing.connector_type = entity.connector_type.value
            existing.host = entity.host
            existing.port = entity.port
            existing.database_name = entity.database_name
            existing.credentials = _encrypt_credentials(self._credentials_to_dict(entity.credentials))
            existing.extra_params = entity.extra_params
            existing.status = entity.status.value
            existing.last_tested_at = entity.last_tested_at
            existing.updated_at = datetime.now(timezone.utc)
            await self._session.flush()
            return self._to_entity(existing)
        else:
            model = self._to_model(entity)
            self._session.add(model)
            await self._session.flush()
            return self._to_entity(model)

    async def delete(self, entity_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(ConnectionModel).where(ConnectionModel.id == entity_id)
        )

    async def list(self, limit: int = 100, offset: int = 0) -> list[Connection]:
        result = await self._session.execute(
            select(ConnectionModel).limit(limit).offset(offset).order_by(ConnectionModel.created_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_project_id(
        self, project_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> list[Connection]:
        result = await self._session.execute(
            select(ConnectionModel)
            .where(ConnectionModel.project_id == project_id)
            .limit(limit)
            .offset(offset)
            .order_by(ConnectionModel.created_at.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_project_id(self, project_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(ConnectionModel).where(ConnectionModel.project_id == project_id)
        )
        return result.scalar_one()

    def _to_entity(self, model: ConnectionModel) -> Connection:
        creds = _decrypt_credentials(model.credentials or {})
        return Connection(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            connector_type=ConnectorType(model.connector_type),
            host=model.host,
            port=model.port,
            database_name=model.database_name,
            credentials=ConnectionCredentials(
                username=creds.get("username", ""),
                password=creds.get("password", ""),
                extra=creds.get("extra", {}),
            ),
            extra_params=model.extra_params or {},
            status=ConnectionStatus(model.status),
            last_tested_at=model.last_tested_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Connection) -> ConnectionModel:
        return ConnectionModel(
            id=entity.id,
            project_id=entity.project_id,
            name=entity.name,
            connector_type=entity.connector_type.value,
            host=entity.host,
            port=entity.port,
            database_name=entity.database_name,
            credentials=_encrypt_credentials(self._credentials_to_dict(entity.credentials)),
            extra_params=entity.extra_params,
            status=entity.status.value,
            last_tested_at=entity.last_tested_at,
        )

    @staticmethod
    def _credentials_to_dict(creds: ConnectionCredentials) -> dict:
        return {
            "username": creds.username,
            "password": creds.password,
            "extra": creds.extra,
        }
