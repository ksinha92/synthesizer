"""Discovery queries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class GetDiscoveryResultsQuery:
    connection_id: uuid.UUID


@dataclass(frozen=True)
class GetPIIClassificationsQuery:
    schema_id: uuid.UUID
    min_confidence: float = 0.0
    pii_type: str | None = None
    classification: str | None = None


@dataclass(frozen=True)
class GetRelationshipsQuery:
    schema_id: uuid.UUID
