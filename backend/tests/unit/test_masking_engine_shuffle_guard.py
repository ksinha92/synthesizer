"""Defensive guards around SHUFFLE in the joint-masking path."""

from __future__ import annotations

import pytest

from app.infrastructure.engine.masking_engine import MaskingEngine
from app.domain.masking.value_objects import MaskingStrategy


def test_mask_row_rejects_shuffle_strategy():
    """mask_row must refuse SHUFFLE — mask_value returns the value unchanged
    for SHUFFLE, so silently letting it through would no-op the rule."""
    engine = MaskingEngine(salt="s")
    rules = [
        {"column_name": "x", "masking_type": MaskingStrategy.SHUFFLE.value},
    ]
    with pytest.raises(ValueError, match="SHUFFLE"):
        engine.mask_row({"x": "abc"}, rules)


def test_mask_row_rejects_shuffle_even_when_other_rules_are_joint():
    """A SHUFFLE rule mixed with a consistency-grouped HASH rule still raises;
    callers must split the batch."""
    engine = MaskingEngine(salt="s")
    rules = [
        {"column_name": "y", "masking_type": MaskingStrategy.HASH.value,
         "consistency_group": "g"},
        {"column_name": "x", "masking_type": MaskingStrategy.SHUFFLE.value},
    ]
    with pytest.raises(ValueError, match="SHUFFLE"):
        engine.mask_row({"x": "abc", "y": "dup"}, rules)


def test_mask_row_no_shuffle_runs_unchanged():
    engine = MaskingEngine(salt="s")
    rules = [
        {"column_name": "x", "masking_type": MaskingStrategy.HASH.value,
         "consistency_group": "g"},
    ]
    out = engine.mask_row({"x": "abc"}, rules)
    assert out["x"] != "abc"
