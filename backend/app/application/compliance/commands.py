"""Compliance commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerateReportCommand:
    project_id: uuid.UUID
    regulation: str  # hipaa | gdpr | ccpa
    user_id: uuid.UUID
