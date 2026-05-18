"""Synthetic domain entities. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.domain.shared.entity import AggregateRoot
from app.domain.synthetic.value_objects import GenerationMethod


@dataclass
class SyntheticConfig(AggregateRoot):
    """Configuration for synthetic data generation."""

    project_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    name: str = ""
    # May be None if the source connection was deleted (FK ON DELETE SET NULL).
    # Callers must reassign a source before preview/generate can run.
    source_connection_id: uuid.UUID | None = None
    target_connection_id: uuid.UUID | None = None
    tables: list[dict] = field(default_factory=list)  # [{table_name, row_count, columns: [...]}]
    generation_method: GenerationMethod = GenerationMethod.FAKER
    config: dict = field(default_factory=dict)  # Engine-specific config (seed, locale, etc.)
    nlp_prompt: str | None = None
    row_count: int = 100
    status: str = "draft"
