"""Synthetic queries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class GetConfigQuery:
    config_id: uuid.UUID


@dataclass(frozen=True)
class ListConfigsQuery:
    project_id: uuid.UUID
