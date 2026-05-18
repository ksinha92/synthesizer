"""SQLAlchemy implementation of FileSchemaRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.synthetic.file_schema_repository import FileSchemaRepository
from app.infrastructure.persistence.models.file_schema import FileSchemaModel


class SQLAlchemyFileSchemaRepository(FileSchemaRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, schema: dict) -> dict:
        schema_id = schema.get("id") or uuid.uuid4()
        if isinstance(schema_id, str):
            schema_id = uuid.UUID(schema_id)

        # Check for existing
        result = await self._session.execute(
            select(FileSchemaModel).where(FileSchemaModel.id == schema_id)
        )
        existing = result.scalar_one_or_none()

        # ``layout_variants`` lives inside metadata JSONB so the existing
        # table schema needs no migration; we keep it visible to writers
        # through a top-level kwarg, and the reader surfaces it back as a
        # peer of ``fields`` (see _to_dict).
        merged_metadata = dict(schema.get("metadata") or {})
        if "layout_variants" in schema and schema["layout_variants"] is not None:
            merged_metadata["layout_variants"] = schema["layout_variants"]

        if existing:
            existing.name = schema["name"]
            existing.file_format = schema["file_format"]
            existing.encoding = schema.get("encoding", "ascii")
            existing.record_length = schema.get("record_length", 0)
            existing.has_rdw = schema.get("has_rdw", False)
            existing.output_filename = schema.get("output_filename")
            existing.fields = schema["fields"]
            existing.metadata_ = merged_metadata or None
            await self._session.flush()
            return self._to_dict(existing)
        else:
            model = FileSchemaModel(
                id=schema_id,
                project_id=schema["project_id"],
                name=schema["name"],
                file_format=schema["file_format"],
                encoding=schema.get("encoding", "ascii"),
                record_length=schema.get("record_length", 0),
                has_rdw=schema.get("has_rdw", False),
                output_filename=schema.get("output_filename"),
                fields=schema["fields"],
                metadata_=merged_metadata or None,
            )
            self._session.add(model)
            await self._session.flush()
            return self._to_dict(model)

    async def get(self, schema_id: uuid.UUID) -> dict | None:
        result = await self._session.execute(
            select(FileSchemaModel).where(FileSchemaModel.id == schema_id)
        )
        model = result.scalar_one_or_none()
        return self._to_dict(model) if model else None

    async def list_by_project(self, project_id: uuid.UUID) -> list[dict]:
        result = await self._session.execute(
            select(FileSchemaModel)
            .where(FileSchemaModel.project_id == project_id)
            .order_by(FileSchemaModel.created_at.desc())
        )
        return [self._to_dict(m) for m in result.scalars().all()]

    async def delete(self, schema_id: uuid.UUID) -> None:
        await self._session.execute(
            sa_delete(FileSchemaModel).where(FileSchemaModel.id == schema_id)
        )

    @staticmethod
    def _to_dict(model: FileSchemaModel) -> dict:
        metadata = dict(model.metadata_ or {})
        # Lift layout_variants out of the metadata blob so the frontend can
        # consume it as a top-level field. The metadata copy keeps a soft
        # backstop entry so legacy readers still work.
        layout_variants = metadata.get("layout_variants") or []
        return {
            "id": str(model.id),
            "project_id": str(model.project_id),
            "name": model.name,
            "file_format": model.file_format,
            "encoding": model.encoding,
            "record_length": model.record_length,
            "has_rdw": model.has_rdw,
            "output_filename": model.output_filename,
            "fields": model.fields,
            "metadata": metadata or None,
            "layout_variants": layout_variants,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }
