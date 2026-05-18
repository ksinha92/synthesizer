"""Discovery commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RunDiscoveryCommand:
    connection_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class OverridePIIClassificationCommand:
    column_id: uuid.UUID
    pii_type: str
    classification: str
    user_id: uuid.UUID
    note: str = ""
