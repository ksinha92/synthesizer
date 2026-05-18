"""Connection commands (write operations)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CreateConnectionCommand:
    project_id: uuid.UUID
    name: str
    connector_type: str
    host: str
    port: int
    database_name: str
    username: str = ""
    password: str = ""
    extra_params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TestConnectionCommand:
    connection_id: uuid.UUID


@dataclass(frozen=True)
class UpdateConnectionCommand:
    connection_id: uuid.UUID
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    password: str | None = None
    extra_params: dict | None = None


@dataclass(frozen=True)
class DeleteConnectionCommand:
    connection_id: uuid.UUID
