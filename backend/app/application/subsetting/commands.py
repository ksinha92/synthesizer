"""Subsetting commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CreateSubsetConfigCommand:
    project_id: uuid.UUID
    name: str
    source_connection_id: uuid.UUID
    target_percentage: float | None = None
    target_row_count: int | None = None
    root_tables: list[dict] = field(default_factory=list)
    traversal_strategy: str = "upstream"
    output_mode: str = "same_database"


@dataclass(frozen=True)
class AnalyzeSubsetCommand:
    config_id: uuid.UUID


@dataclass(frozen=True)
class ExecuteSubsetCommand:
    config_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
