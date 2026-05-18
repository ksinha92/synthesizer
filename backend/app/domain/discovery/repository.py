"""Discovery repository ABC. No framework dependencies."""

from __future__ import annotations

import uuid
from abc import abstractmethod

from app.domain.discovery.entities import (
    DiscoveredColumn,
    DiscoveredRelationship,
    DiscoveredSchema,
    DiscoveredTable,
)
from app.domain.discovery.value_objects import Classification, PIIType
from app.domain.shared.repository import Repository


class DiscoveryRepository(Repository[DiscoveredSchema]):
    """Abstract repository for discovery aggregates."""

    @abstractmethod
    async def find_by_connection_id(self, connection_id: uuid.UUID) -> list[DiscoveredSchema]:
        ...

    @abstractmethod
    async def save_schema_tree(
        self,
        schema: DiscoveredSchema,
        tables: list[DiscoveredTable],
        columns: list[DiscoveredColumn],
    ) -> DiscoveredSchema:
        ...

    @abstractmethod
    async def get_tables_by_schema_id(self, schema_id: uuid.UUID) -> list[DiscoveredTable]:
        ...

    @abstractmethod
    async def get_columns_by_table_id(self, table_id: uuid.UUID) -> list[DiscoveredColumn]:
        ...

    @abstractmethod
    async def get_pii_columns(
        self, schema_id: uuid.UUID, min_confidence: float = 0.0
    ) -> list[DiscoveredColumn]:
        ...

    @abstractmethod
    async def update_column_classification(
        self,
        column_id: uuid.UUID,
        pii_type: PIIType,
        classification: Classification,
        override_by: uuid.UUID | None = None,
        override_note: str | None = None,
    ) -> DiscoveredColumn:
        ...

    @abstractmethod
    async def save_relationships(self, relationships: list[DiscoveredRelationship]) -> None:
        ...

    @abstractmethod
    async def get_relationships(self, schema_id: uuid.UUID) -> list[DiscoveredRelationship]:
        ...
