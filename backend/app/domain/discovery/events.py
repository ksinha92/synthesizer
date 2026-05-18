"""Discovery domain events. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.shared.event import DomainEvent


@dataclass(frozen=True)
class DiscoveryCompleted(DomainEvent):
    """Emitted when schema discovery finishes successfully."""

    connection_id: uuid.UUID = None  # type: ignore[assignment]
    schema_count: int = 0
    table_count: int = 0
    column_count: int = 0
    pii_count: int = 0


@dataclass(frozen=True)
class PIIDetected(DomainEvent):
    """Emitted when PII is detected in a column."""

    column_id: uuid.UUID = None  # type: ignore[assignment]
    pii_type: str = ""
    confidence: float = 0.0
