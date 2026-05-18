"""File schema ORM model."""

import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FileSchemaModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "file_schemas"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(50), nullable=False)
    encoding: Mapped[str] = mapped_column(String(50), nullable=False, default="ascii")
    record_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_rdw: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fields: Mapped[list] = mapped_column(JSONB, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
