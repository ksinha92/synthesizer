"""Masking commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CreatePolicyCommand:
    project_id: uuid.UUID
    name: str
    description: str = ""
    is_default: bool = False


@dataclass(frozen=True)
class AddRuleCommand:
    policy_id: uuid.UUID
    column_id: uuid.UUID | None = None
    match_pattern: dict | None = None
    masking_type: str = "redact"
    masking_config: dict = field(default_factory=dict)
    preserve_format: bool = False
    deterministic: bool = False
    # Phase 53/58: linked-column joint generation + consistency-group identity.
    linked_column_ids: list[uuid.UUID] = field(default_factory=list)
    consistency_group: str | None = None


@dataclass(frozen=True)
class PreviewMaskingCommand:
    policy_id: uuid.UUID
    connection_id: uuid.UUID
    table_name: str
    schema_name: str = "public"


@dataclass(frozen=True)
class ExecuteMaskingCommand:
    policy_id: uuid.UUID
    project_id: uuid.UUID
    connection_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class AutoSuggestRulesCommand:
    project_id: uuid.UUID
    schema_id: uuid.UUID
