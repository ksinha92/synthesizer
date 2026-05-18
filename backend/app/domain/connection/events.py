"""Connection domain events. No framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.shared.event import DomainEvent


@dataclass(frozen=True)
class ConnectionTested(DomainEvent):
    """Emitted when a connection test succeeds."""
    pass


@dataclass(frozen=True)
class ConnectionFailed(DomainEvent):
    """Emitted when a connection test fails."""

    error_message: str = ""
