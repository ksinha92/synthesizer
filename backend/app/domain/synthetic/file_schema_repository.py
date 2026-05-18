"""File schema repository ABC. No framework dependencies."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class FileSchemaRepository(ABC):
    """Abstract repository for file schema persistence.

    Uses dict in/out since FileSchemaDefinition is a value object, not an entity.
    Storage wraps it with id, project_id, and timestamps.
    """

    @abstractmethod
    async def save(self, schema: dict) -> dict:
        """Persist a file schema. Returns the stored record with id and timestamps."""
        ...

    @abstractmethod
    async def get(self, schema_id: uuid.UUID) -> dict | None:
        """Retrieve a file schema by ID."""
        ...

    @abstractmethod
    async def list_by_project(self, project_id: uuid.UUID) -> list[dict]:
        """List all file schemas for a project."""
        ...

    @abstractmethod
    async def delete(self, schema_id: uuid.UUID) -> None:
        """Delete a file schema by ID."""
        ...
