"""Base entity classes for domain layer. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Entity:
    """Base entity with identity and timestamps."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class AggregateRoot(Entity):
    """Base aggregate root. Collects domain events for dispatch after persistence."""

    _events: list = field(default_factory=list, repr=False, compare=False)

    def add_event(self, event: object) -> None:
        self._events.append(event)

    def collect_events(self) -> list:
        events = list(self._events)
        self._events.clear()
        return events
