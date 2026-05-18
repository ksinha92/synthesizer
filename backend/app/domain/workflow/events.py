"""Workflow domain events. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.shared.event import DomainEvent


@dataclass(frozen=True)
class WorkflowStepCompleted(DomainEvent):
    workflow_id: uuid.UUID = None  # type: ignore[assignment]
    node_id: str = ""
    node_type: str = ""
    status: str = ""


@dataclass(frozen=True)
class WorkflowCompleted(DomainEvent):
    workflow_id: uuid.UUID = None  # type: ignore[assignment]
    node_count: int = 0
    duration_ms: int = 0
