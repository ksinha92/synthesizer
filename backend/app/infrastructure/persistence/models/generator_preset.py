"""Generator preset ORM model (migration 017)."""


from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GeneratorPresetModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "generator_presets"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    generator_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    consistency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
