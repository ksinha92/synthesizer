"""Synthetic commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CreateSyntheticConfigCommand:
    project_id: uuid.UUID
    name: str
    source_connection_id: uuid.UUID
    generation_method: str = "faker"
    tables: list[dict] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    nlp_prompt: str | None = None
    row_count: int = 100


@dataclass(frozen=True)
class GenerateCommand:
    config_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class PreviewCommand:
    config_id: uuid.UUID
    limit: int = 10
