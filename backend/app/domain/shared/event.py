"""Base domain event for cross-context communication. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    """Base domain event. Immutable, timestamped, tied to an aggregate."""

    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    aggregate_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
