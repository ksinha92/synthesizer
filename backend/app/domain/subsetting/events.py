"""Subsetting domain events. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.shared.event import DomainEvent


@dataclass(frozen=True)
class SubsetCompleted(DomainEvent):
    config_id: uuid.UUID = None  # type: ignore[assignment]
    table_count: int = 0
    total_rows: int = 0
