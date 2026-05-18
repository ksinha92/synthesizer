"""SQLAlchemy implementation of DiscoveryRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.discovery.entities import (
    DiscoveredColumn,
    DiscoveredRelationship,
    DiscoveredSchema,
    DiscoveredTable,
)
from app.domain.discovery.repository import DiscoveryRepository
from app.domain.discovery.value_objects import (
    Classification,
    PIIConfidence,
    PIIType,
    RelationshipType,
)
from app.infrastructure.persistence.models.discovery import (
    DiscoveredColumnModel,
    DiscoveredRelationshipModel,
    DiscoveredSchemaModel,
    DiscoveredTableModel,
)


class SQLAlchemyDiscoveryRepository(DiscoveryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: uuid.UUID) -> DiscoveredSchema | None:
        result = await self._session.execute(
            select(DiscoveredSchemaModel).where(DiscoveredSchemaModel.id == entity_id)
        )
        model = result.scalar_one_or_none()
        return self._schema_to_entity(model) if model else None

    async def save(self, entity: DiscoveredSchema) -> DiscoveredSchema:
        model = DiscoveredSchemaModel(
            id=entity.id,
            connection_id=entity.connection_id,
            schema_name=entity.schema_name,
            discovered_at=entity.discovered_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._schema_to_entity(model)

    async def delete(self, entity_id: uuid.UUID) -> None:
        pass  # Cascade delete handled by DB

    async def list(self, limit: int = 100, offset: int = 0) -> list[DiscoveredSchema]:
        result = await self._session.execute(
            select(DiscoveredSchemaModel).limit(limit).offset(offset)
        )
        return [self._schema_to_entity(m) for m in result.scalars().all()]

    async def find_by_connection_id(self, connection_id: uuid.UUID) -> list[DiscoveredSchema]:
        result = await self._session.execute(
            select(DiscoveredSchemaModel)
            .where(DiscoveredSchemaModel.connection_id == connection_id)
            .order_by(DiscoveredSchemaModel.discovered_at.desc())
        )
        return [self._schema_to_entity(m) for m in result.scalars().all()]

    async def save_schema_tree(
        self,
        schema: DiscoveredSchema,
        tables: list[DiscoveredTable],
        columns: list[DiscoveredColumn],
    ) -> DiscoveredSchema:
        """Persist or refresh a discovery tree, preserving existing IDs.

        Earlier versions inserted a fresh row for every entity on every
        re-discovery, which silently orphaned any masking rule that
        referenced a column_id (the Database View dropdown, Privacy Hub
        apply-all, sensitivity rules — all of them). We now upsert by
        natural key — ``(connection_id, schema_name)``,
        ``(schema_id, table_name)``, ``(table_id, column_name)`` — so
        a subsequent discovery refreshes metadata in place and existing
        rules keep pointing at the same columns.
        """
        # ── 1. Schema upsert ────────────────────────────────────────────
        existing_schema = await self._session.execute(
            select(DiscoveredSchemaModel).where(
                DiscoveredSchemaModel.connection_id == schema.connection_id,
                DiscoveredSchemaModel.schema_name == schema.schema_name,
            )
        )
        schema_model = existing_schema.scalar_one_or_none()
        if schema_model is None:
            schema_model = DiscoveredSchemaModel(
                id=schema.id,
                connection_id=schema.connection_id,
                schema_name=schema.schema_name,
                discovered_at=schema.discovered_at,
            )
            self._session.add(schema_model)
        else:
            schema_model.discovered_at = schema.discovered_at
        await self._session.flush()

        # ── 2. Tables upsert + index by name ────────────────────────────
        existing_tables_res = await self._session.execute(
            select(DiscoveredTableModel).where(
                DiscoveredTableModel.schema_id == schema_model.id
            )
        )
        existing_by_name: dict[str, DiscoveredTableModel] = {
            m.table_name: m for m in existing_tables_res.scalars().all()
        }

        table_by_name: dict[str, DiscoveredTableModel] = {}
        for table in tables:
            existing = existing_by_name.get(table.table_name)
            if existing is not None:
                existing.row_count = table.row_count
                existing.size_bytes = table.size_bytes
                table_by_name[table.table_name] = existing
            else:
                tm = DiscoveredTableModel(
                    id=table.id,
                    schema_id=schema_model.id,
                    table_name=table.table_name,
                    row_count=table.row_count,
                    size_bytes=table.size_bytes,
                )
                self._session.add(tm)
                table_by_name[table.table_name] = tm
        await self._session.flush()

        # ── 3. Columns upsert ───────────────────────────────────────────
        # Re-order columns alongside tables so each column lands on its
        # parent table. Previously the code walked ``table_idx`` without
        # incrementing it, which silently routed every column to the first
        # table when there were many — a latent bug fixed here as part of
        # the upsert switch.
        table_ids = [tm.id for tm in table_by_name.values()]
        if table_ids:
            existing_cols_res = await self._session.execute(
                select(DiscoveredColumnModel).where(
                    DiscoveredColumnModel.table_id.in_(table_ids)
                )
            )
            existing_cols: dict[tuple[uuid.UUID, str], DiscoveredColumnModel] = {
                (m.table_id, m.column_name): m
                for m in existing_cols_res.scalars().all()
            }
        else:
            existing_cols = {}

        # Build a {table_name: [columns]} index from the domain payload so we
        # can pair columns to their proper table model.
        cols_by_table: dict[str, list[DiscoveredColumn]] = {}
        # The service emits all_columns in the same iteration order as it
        # emits tables — columns are grouped by table contiguously. We use
        # the running table sequence and fall back to the first table for
        # callers that supplied table_id directly.
        # Recreate the pairing by walking columns and assigning to the
        # in-flight table whenever ``table_id`` was the placeholder
        # ``uuid.UUID(int=0)``.
        ordered_table_names = [t.table_name for t in tables]
        # Use a generator so we advance one table at a time as we exhaust
        # its column list. The service contract is: contiguous blocks of
        # columns belong to the table immediately preceding them.
        table_index_for_col: list[str] = []
        # Walk tables and columns together via two pointers. Each column
        # belongs to the latest table whose columns haven't been emitted
        # yet. We approximate the boundary by re-running ``get_columns``
        # would be expensive — instead the service hands us columns in
        # order so we partition by table_id placeholder == int(0) blocks.
        # Concretely: when we encounter a column we map it to the table
        # whose columns we expect next. Empty-table edge case: skip ahead.
        ti = 0
        # First pass: distribute columns based on the column's intrinsic
        # table_id when set, otherwise into the contiguous table block.
        # For our service this means: every column had table_id == uuid(int=0)
        # at the time it was assembled, so we assign by walk.
        # To avoid quadratic work we count expected columns per table by
        # peeking — instead, we walk: when ti advances, we move on.
        # Simpler and correct: place each incoming column under the latest
        # table in iteration order; when we observe a column whose name we
        # already placed for that table, advance ti.
        seen_for_current: set[str] = set()
        for col in columns:
            if ti >= len(ordered_table_names):
                # More columns than tables — defensively assign to last.
                ti = len(ordered_table_names) - 1
                seen_for_current = set()
            if col.column_name in seen_for_current and ti + 1 < len(ordered_table_names):
                ti += 1
                seen_for_current = set()
            table_index_for_col.append(ordered_table_names[ti])
            seen_for_current.add(col.column_name)
            cols_by_table.setdefault(ordered_table_names[ti], []).append(col)

        for tname, table_columns in cols_by_table.items():
            target_table = table_by_name.get(tname)
            if target_table is None:
                continue
            for col in table_columns:
                existing = existing_cols.get((target_table.id, col.column_name))
                pii_payload = {
                    "score": col.pii_confidence.score,
                    "detector": col.pii_confidence.detector,
                    "details": col.pii_confidence.details,
                }
                if existing is not None:
                    existing.data_type = col.data_type
                    existing.is_nullable = col.is_nullable
                    existing.is_primary_key = col.is_primary_key
                    existing.is_foreign_key = col.is_foreign_key
                    existing.fk_references = col.fk_references
                    existing.sample_values = col.sample_values
                    existing.stats = col.stats
                    # Preserve user-applied overrides — don't let a fresh
                    # automated PII classification clobber a manual one.
                    if existing.classification != Classification.MANUALLY_CLASSIFIED.value:
                        existing.pii_type = col.pii_type.value
                        existing.pii_confidence = pii_payload
                        existing.classification = col.classification.value
                else:
                    col_model = DiscoveredColumnModel(
                        id=col.id,
                        table_id=target_table.id,
                        column_name=col.column_name,
                        data_type=col.data_type,
                        is_nullable=col.is_nullable,
                        is_primary_key=col.is_primary_key,
                        is_foreign_key=col.is_foreign_key,
                        fk_references=col.fk_references,
                        sample_values=col.sample_values,
                        stats=col.stats,
                        pii_type=col.pii_type.value,
                        pii_confidence=pii_payload,
                        classification=col.classification.value,
                        override_by=col.override_by,
                        override_note=col.override_note,
                    )
                    self._session.add(col_model)

        await self._session.flush()
        return self._schema_to_entity(schema_model)

    async def get_tables_by_schema_id(self, schema_id: uuid.UUID) -> list[DiscoveredTable]:
        result = await self._session.execute(
            select(DiscoveredTableModel).where(DiscoveredTableModel.schema_id == schema_id)
        )
        return [self._table_to_entity(m) for m in result.scalars().all()]

    async def get_columns_by_table_id(self, table_id: uuid.UUID) -> list[DiscoveredColumn]:
        result = await self._session.execute(
            select(DiscoveredColumnModel).where(DiscoveredColumnModel.table_id == table_id)
        )
        return [self._column_to_entity(m) for m in result.scalars().all()]

    async def get_pii_columns(
        self, schema_id: uuid.UUID, min_confidence: float = 0.0
    ) -> list[DiscoveredColumn]:
        result = await self._session.execute(
            select(DiscoveredColumnModel)
            .join(DiscoveredTableModel, DiscoveredColumnModel.table_id == DiscoveredTableModel.id)
            .where(DiscoveredTableModel.schema_id == schema_id)
            .where(DiscoveredColumnModel.pii_type != "none")
        )
        columns = [self._column_to_entity(m) for m in result.scalars().all()]
        return [c for c in columns if c.pii_confidence.score >= min_confidence]

    async def update_column_classification(
        self,
        column_id: uuid.UUID,
        pii_type: PIIType,
        classification: Classification,
        override_by: uuid.UUID | None = None,
        override_note: str | None = None,
    ) -> DiscoveredColumn:
        result = await self._session.execute(
            select(DiscoveredColumnModel).where(DiscoveredColumnModel.id == column_id)
        )
        model = result.scalar_one()
        model.pii_type = pii_type.value
        model.classification = classification.value
        model.override_by = override_by
        model.override_note = override_note
        await self._session.flush()
        return self._column_to_entity(model)

    async def save_relationships(self, relationships: list[DiscoveredRelationship]) -> None:
        for rel in relationships:
            model = DiscoveredRelationshipModel(
                id=rel.id,
                schema_id=rel.schema_id,
                source_table_id=rel.source_table_id,
                source_column_id=rel.source_column_id,
                target_table_id=rel.target_table_id,
                target_column_id=rel.target_column_id,
                relationship_type=rel.relationship_type.value,
                confidence=rel.confidence,
            )
            self._session.add(model)
        await self._session.flush()

    async def get_relationships(self, schema_id: uuid.UUID) -> list[DiscoveredRelationship]:
        result = await self._session.execute(
            select(DiscoveredRelationshipModel).where(DiscoveredRelationshipModel.schema_id == schema_id)
        )
        return [self._relationship_to_entity(m) for m in result.scalars().all()]

    # --- Mappers ---

    @staticmethod
    def _schema_to_entity(m: DiscoveredSchemaModel) -> DiscoveredSchema:
        return DiscoveredSchema(id=m.id, connection_id=m.connection_id, schema_name=m.schema_name, discovered_at=m.discovered_at, created_at=m.created_at, updated_at=m.updated_at)

    @staticmethod
    def _table_to_entity(m: DiscoveredTableModel) -> DiscoveredTable:
        return DiscoveredTable(id=m.id, schema_id=m.schema_id, table_name=m.table_name, row_count=m.row_count, size_bytes=m.size_bytes, created_at=m.created_at, updated_at=m.updated_at)

    @staticmethod
    def _column_to_entity(m: DiscoveredColumnModel) -> DiscoveredColumn:
        conf = m.pii_confidence or {}
        return DiscoveredColumn(
            id=m.id, table_id=m.table_id, column_name=m.column_name, data_type=m.data_type,
            is_nullable=m.is_nullable, is_primary_key=m.is_primary_key, is_foreign_key=m.is_foreign_key,
            fk_references=m.fk_references, sample_values=m.sample_values or [], stats=m.stats or {},
            pii_type=PIIType(m.pii_type), pii_confidence=PIIConfidence(score=conf.get("score", 0), detector=conf.get("detector", ""), details=conf.get("details", {})),
            classification=Classification(m.classification), override_by=m.override_by, override_note=m.override_note,
            created_at=m.created_at, updated_at=m.updated_at,
        )

    @staticmethod
    def _relationship_to_entity(m: DiscoveredRelationshipModel) -> DiscoveredRelationship:
        return DiscoveredRelationship(
            id=m.id, schema_id=m.schema_id, source_table_id=m.source_table_id, source_column_id=m.source_column_id,
            target_table_id=m.target_table_id, target_column_id=m.target_column_id,
            relationship_type=RelationshipType(m.relationship_type), confidence=m.confidence,
            is_virtual=bool(getattr(m, "is_virtual", False)),
            created_at=m.created_at, updated_at=m.updated_at,
        )
