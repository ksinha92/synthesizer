"""Masking domain entities. No framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.domain.shared.entity import AggregateRoot, Entity
from app.domain.masking.value_objects import MaskingStrategy


@dataclass
class MaskingPolicy(AggregateRoot):
    project_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    name: str = ""
    description: str = ""
    is_default: bool = False


@dataclass
class MaskingRule(Entity):
    policy_id: uuid.UUID = field(default_factory=lambda: uuid.UUID(int=0))
    column_id: uuid.UUID | None = None
    match_pattern: dict | None = None  # Match by PII type or column name pattern
    masking_type: MaskingStrategy = MaskingStrategy.REDACT
    masking_config: dict = field(default_factory=dict)
    preserve_format: bool = False
    deterministic: bool = False
    # Phase 51: optional generator preset reference (preset.config overrides masking_config).
    preset_id: uuid.UUID | None = None
    # Phase 53: linked-column joint generation + consistency-group identity.
    linked_column_ids: list[uuid.UUID] = field(default_factory=list)
    consistency_group: str | None = None
