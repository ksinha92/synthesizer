"""Connection ORM model. Infrastructure layer — maps to/from domain entities."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConnectionModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connections"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str] = mapped_column(String(500), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Credentials stored as Fernet-encrypted JSONB: {"_encrypted": "base64_ciphertext"}
    # Encryption/decryption handled transparently in connection_repo.py
    credentials: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    extra_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="untested")
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
