"""Compliance domain entities. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.shared.entity import AggregateRoot


@dataclass
class ComplianceReport(AggregateRoot):
    project_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    report_type: str = ""  # hipaa | gdpr | ccpa
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    summary: dict = field(default_factory=dict)  # Summary metadata (column_count, coverage_pct)
    storage_path: str = ""  # Path to full report in storage backend
    created_by: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    # Phase 57 F1/migration 022: marks pre-v0.9 reports generated against the
    # empty-payload bug. Surfaces in the GET /reports response so callers can
    # warn users that the artifact is incomplete.
    legacy: bool = False
