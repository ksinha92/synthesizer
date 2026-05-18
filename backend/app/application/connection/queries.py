"""Connection queries (read operations)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class GetConnectionQuery:
    connection_id: uuid.UUID


@dataclass(frozen=True)
class ListConnectionsQuery:
    project_id: uuid.UUID
    limit: int = 50
    offset: int = 0
