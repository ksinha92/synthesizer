"""Discovery domain services. No framework dependencies."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import structlog

from app.domain.discovery.entities import (
    DiscoveredColumn,
    DiscoveredRelationship,
    DiscoveredSchema,
    DiscoveredTable,
)
from app.domain.discovery.events import DiscoveryCompleted
from app.domain.discovery.value_objects import PIIType, RelationshipType

logger = structlog.get_logger()

# Regex patterns for masking sample values before storage
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_SSN_RE = re.compile(r"\d{3}-\d{2}-\d{4}")
_PHONE_RE = re.compile(r"(\+?1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_CC_RE = re.compile(r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}")

MAX_SAMPLE_VALUES = 5
MAX_SAMPLE_LENGTH = 50


class SchemaDiscoveryService:
    """Orchestrates schema introspection and builds discovery entities."""

    def __init__(self, connector_registry, discovery_repository):
        self._registry = connector_registry
        self._repository = discovery_repository

    async def discover(
        self,
        connection,
        custom_rules: list[dict] | None = None,
    ) -> DiscoveredSchema:
        """Run full schema introspection on a connection.

        If ``custom_rules`` is provided, ALL rule strategies are evaluated
        together in user-defined priority order against the column name and
        raw sample values, BEFORE ``_mask_sample_values`` redacts the samples.
        This is the single place precedence is honored across all rule
        types; the detector falls back to column-name-only matching for any
        column that arrives here without an upstream classification.
        """
        rules = [r for r in (custom_rules or []) if r.get("enabled", True)]

        connector = self._registry.get_connector(
            connector_type=connection.connector_type,
            host=connection.host,
            port=connection.port,
            database_name=connection.database_name,
            username=connection.credentials.username,
            password=connection.credentials.password,
            extra_params=connection.extra_params,
        )

        all_tables = []
        all_columns = []

        try:
            schemas = await connector.get_schemas()

            for schema_info in schemas:
                schema_name = schema_info["name"]
                tables = await connector.get_tables(schema_name)

                for table_info in tables:
                    table = DiscoveredTable(
                        schema_id=uuid.UUID(int=0),  # Set after schema saved
                        table_name=table_info["name"],
                        row_count=table_info.get("row_count", 0),
                        size_bytes=table_info.get("size_bytes", 0),
                    )
                    all_tables.append(table)

                    columns = await connector.get_columns(schema_name, table_info["name"])

                    # Get sample data for PII detection
                    try:
                        samples = await connector.get_sample_data(
                            schema_name, table_info["name"], limit=5
                        )
                    except Exception:
                        samples = []

                    for col_info in columns:
                        col_samples = [
                            row.get(col_info["name"])
                            for row in samples
                            if col_info["name"] in row
                        ]

                        # Layer 0 — evaluate ALL custom rules together in
                        # priority order against raw samples + column name.
                        # This is the only place precedence can be honored
                        # across both column-name and value-regex strategies,
                        # since the detector sees only masked samples.
                        rule_hit = None
                        if rules:
                            from app.infrastructure.ai.custom_rules import (
                                match_all_rules,
                            )
                            rule_hit = match_all_rules(
                                col_info["name"], col_samples, rules
                            )

                        column = DiscoveredColumn(
                            table_id=uuid.UUID(int=0),  # Set after table saved
                            column_name=col_info["name"],
                            data_type=col_info["data_type"],
                            is_nullable=col_info.get("is_nullable", True),
                            is_primary_key=col_info.get("is_primary_key", False),
                            is_foreign_key=col_info.get("is_foreign_key", False),
                            fk_references=col_info.get("fk_references"),
                            sample_values=_mask_sample_values(col_samples),
                            # Carry per-column connector hints (e.g. MongoDB
                            # ``mixed_types`` distribution) through to the
                            # repository so the Database View can render them.
                            stats=col_info.get("stats") or {},
                        )
                        if rule_hit is not None:
                            from app.domain.discovery.value_objects import (
                                Classification,
                                PIIConfidence,
                            )

                            matched_type, matched_score = rule_hit
                            column.pii_type = matched_type
                            column.pii_confidence = PIIConfidence(
                                score=matched_score,
                                detector="custom_rule",
                            )
                            column.classification = Classification.AUTO_CLASSIFIED
                        all_columns.append(column)

            # Create and persist schema
            schema = DiscoveredSchema(
                connection_id=connection.id,
                schema_name=schemas[0]["name"] if schemas else "public",
                discovered_at=datetime.now(timezone.utc),
            )

            saved_schema = await self._repository.save_schema_tree(
                schema, all_tables, all_columns
            )

            # Build relationships from FK references
            relationships = _extract_fk_relationships(saved_schema.id, all_columns, all_tables)
            if relationships:
                await self._repository.save_relationships(relationships)

            pii_count = sum(1 for c in all_columns if c.pii_type != PIIType.NONE)

            saved_schema.add_event(
                DiscoveryCompleted(
                    aggregate_id=saved_schema.id,
                    connection_id=connection.id,
                    schema_count=len(schemas),
                    table_count=len(all_tables),
                    column_count=len(all_columns),
                    pii_count=pii_count,
                )
            )

            await logger.ainfo(
                "discovery_completed",
                connection_id=str(connection.id),
                schemas=len(schemas),
                tables=len(all_tables),
                columns=len(all_columns),
                pii_columns=pii_count,
            )

            return saved_schema

        finally:
            await connector.close()


def _mask_sample_values(values: list) -> list[str]:
    """Mask PII patterns in sample values before storage."""
    masked = []
    for v in values[:MAX_SAMPLE_VALUES]:
        if v is None:
            masked.append("NULL")
            continue
        s = str(v)[:MAX_SAMPLE_LENGTH]
        s = _EMAIL_RE.sub(lambda m: m.group()[0] + "***@" + m.group().split("@")[-1], s)
        s = _SSN_RE.sub("***-**-" + s[-4:] if len(s) >= 4 else "***-**-****", s)
        s = _CC_RE.sub("****-****-****-" + s[-4:] if len(s) >= 4 else "****", s)
        s = _PHONE_RE.sub("***-***-" + s[-4:] if len(s) >= 4 else "***-***-****", s)
        masked.append(s)
    return masked


def _extract_fk_relationships(
    schema_id: uuid.UUID,
    columns: list[DiscoveredColumn],
    tables: list[DiscoveredTable],
) -> list[DiscoveredRelationship]:
    """Extract FK relationships from column metadata."""
    relationships = []
    for col in columns:
        if col.is_foreign_key and col.fk_references:
            relationships.append(
                DiscoveredRelationship(
                    schema_id=schema_id,
                    source_table_id=col.table_id,
                    source_column_id=col.id,
                    target_table_id=uuid.UUID(int=0),  # Resolved during save
                    target_column_id=uuid.UUID(int=0),
                    relationship_type=RelationshipType.FOREIGN_KEY,
                    confidence=1.0,
                )
            )
    return relationships
