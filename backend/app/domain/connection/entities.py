"""Connection aggregate root. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared.entity import AggregateRoot
from app.domain.connection.value_objects import (
    ConnectionCredentials,
    ConnectionStatus,
    ConnectorType,
)


@dataclass
class Connection(AggregateRoot):
    """A data source connection within a project."""

    project_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    name: str = ""
    connector_type: ConnectorType = ConnectorType.POSTGRESQL
    host: str = ""
    port: int = 5432
    database_name: str = ""
    credentials: ConnectionCredentials = field(default_factory=ConnectionCredentials)
    extra_params: dict = field(default_factory=dict)
    status: ConnectionStatus = ConnectionStatus.UNTESTED
    last_tested_at: datetime | None = None
