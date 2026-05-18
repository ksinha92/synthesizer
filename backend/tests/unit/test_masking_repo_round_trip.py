"""Round-trip test: domain MaskingRule entity carries Phase 51/53/54 fields.

Verifies the bug fixed in 56-02 plan 2 doesn't regress — without this
the domain entity dropped preset_id / consistency_group / linked_column_ids,
silently disabling preset-based masking and joint-generation behavior.
"""

from __future__ import annotations

import uuid

import pytest

from app.domain.masking.entities import MaskingRule
from app.domain.masking.value_objects import MaskingStrategy
from app.infrastructure.persistence.models.masking import MaskingRuleModel
from app.infrastructure.persistence.sqlalchemy.masking_repo import (
    SQLAlchemyMaskingRepository,
)


def test_rule_entity_carries_preset_consistency_linked_columns():
    """The dataclass exposes all three new fields with the expected types."""
    rule = MaskingRule(
        policy_id=uuid.uuid4(),
        column_id=uuid.uuid4(),
        masking_type=MaskingStrategy.HASH,
        preset_id=uuid.uuid4(),
        consistency_group="customer_id_group",
        linked_column_ids=[uuid.uuid4(), uuid.uuid4()],
    )
    assert rule.preset_id is not None
    assert rule.consistency_group == "customer_id_group"
    assert len(rule.linked_column_ids) == 2


def test_repo_mapper_carries_preset_consistency_linked_columns():
    """Repository._rule_to_entity must copy the new columns off the model."""
    model = MaskingRuleModel(
        id=uuid.uuid4(),
        policy_id=uuid.uuid4(),
        column_id=uuid.uuid4(),
        match_pattern=None,
        masking_type="hash",
        masking_config={},
        preserve_format=False,
        deterministic=False,
        preset_id=uuid.uuid4(),
        linked_column_ids=[uuid.uuid4()],
        consistency_group="g1",
    )
    entity = SQLAlchemyMaskingRepository._rule_to_entity(model)
    assert entity.preset_id == model.preset_id
    assert entity.consistency_group == "g1"
    assert entity.linked_column_ids == list(model.linked_column_ids)


def test_repo_mapper_handles_legacy_rows_without_new_columns():
    """Old rules with no preset / linked / consistency stay safe to load."""
    model = MaskingRuleModel(
        id=uuid.uuid4(),
        policy_id=uuid.uuid4(),
        column_id=None,
        match_pattern={"pattern": "email"},
        masking_type="redact",
        masking_config={},
        preserve_format=False,
        deterministic=False,
    )
    entity = SQLAlchemyMaskingRepository._rule_to_entity(model)
    assert entity.preset_id is None
    assert entity.consistency_group is None
    assert entity.linked_column_ids == []


class _CaptureSession:
    """Minimal AsyncSession stand-in: capture .add() targets, no-op flush()."""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:  # sync, as on real Session
        self.added.append(obj)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_rule_linked_columns_round_trip():
    """linked_column_ids + consistency_group survive add_rule → _rule_to_entity.

    The plan calls for a full add_rule → get_rules_by_policy round-trip, but
    the unit test suite has no in-process DB fixture. We exercise the write
    path through add_rule() (which is where the regression occurred) and read
    back via the same _rule_to_entity used by get_rules_by_policy. That
    covers the bug surface: dropping the fields anywhere in MaskingRule →
    MaskingRuleModel → MaskingRule would fail this test.
    """
    session = _CaptureSession()
    repo = SQLAlchemyMaskingRepository(session)  # type: ignore[arg-type]

    linked = [uuid.uuid4(), uuid.uuid4()]
    rule = MaskingRule(
        policy_id=uuid.uuid4(),
        column_id=uuid.uuid4(),
        masking_type=MaskingStrategy.HASH,
        masking_config={"salt": "x"},
        linked_column_ids=linked,
        consistency_group="customer-pii",
    )

    saved = await repo.add_rule(rule)

    # add_rule must have written both fields onto the persisted model.
    assert len(session.added) == 1
    persisted = session.added[0]
    assert isinstance(persisted, MaskingRuleModel)
    assert persisted.linked_column_ids == linked
    assert persisted.consistency_group == "customer-pii"

    # And the returned entity (built via _rule_to_entity) must surface them.
    assert saved.linked_column_ids == linked
    assert saved.consistency_group == "customer-pii"


@pytest.mark.asyncio
async def test_rule_add_rule_writes_none_for_empty_linked_columns():
    """Empty linked_column_ids should serialize as NULL (not [] in JSONB)."""
    session = _CaptureSession()
    repo = SQLAlchemyMaskingRepository(session)  # type: ignore[arg-type]

    rule = MaskingRule(
        policy_id=uuid.uuid4(),
        column_id=uuid.uuid4(),
        masking_type=MaskingStrategy.REDACT,
    )
    saved = await repo.add_rule(rule)

    persisted = session.added[0]
    assert persisted.linked_column_ids is None
    assert persisted.consistency_group is None
    assert saved.linked_column_ids == []
    assert saved.consistency_group is None
