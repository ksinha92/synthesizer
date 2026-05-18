"""Compliance domain events. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.shared.event import DomainEvent


@dataclass(frozen=True)
class ComplianceReportGenerated(DomainEvent):
    report_id: uuid.UUID = None  # type: ignore[assignment]
    regulation: str = ""
    project_id: uuid.UUID = None  # type: ignore[assignment]
