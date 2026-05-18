"""Base repository ABC for domain layer. No framework dependencies."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.domain.shared.entity import Entity

T = TypeVar("T", bound=Entity)


class Repository(ABC, Generic[T]):
    """Abstract repository. Infrastructure layer provides implementations."""

    @abstractmethod
    async def get(self, entity_id: uuid.UUID) -> T | None:
        ...

    @abstractmethod
    async def save(self, entity: T) -> T:
        ...

    @abstractmethod
    async def delete(self, entity_id: uuid.UUID) -> None:
        ...

    @abstractmethod
    async def list(self, limit: int = 100, offset: int = 0) -> list[T]:
        ...
