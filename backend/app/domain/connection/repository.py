"""Connection repository ABC. No framework dependencies."""

from __future__ import annotations

import uuid
from abc import abstractmethod

from app.domain.connection.entities import Connection
from app.domain.shared.repository import Repository


class ConnectionRepository(Repository[Connection]):
    """Abstract repository for Connection aggregate."""

    @abstractmethod
    async def find_by_project_id(
        self, project_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> list[Connection]:
        ...
