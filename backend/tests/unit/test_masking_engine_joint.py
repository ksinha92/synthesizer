"""Joint masking — consistency_group + linked_column_names (Phase 56-04)."""

from __future__ import annotations

from app.infrastructure.engine.masking_engine import MaskingEngine
from app.domain.masking.value_objects import MaskingStrategy


def test_consistency_group_yields_same_hash_across_columns():
    engine = MaskingEngine(salt="test-salt")
    a = engine.mask_value("cust-42", MaskingStrategy.HASH, consistency_group="customer_id")
    b = engine.mask_value("cust-42", MaskingStrategy.HASH, consistency_group="customer_id")
    assert a == b, "same value + same group → same hash"


def test_consistency_group_differs_from_no_group():
    engine = MaskingEngine(salt="test-salt")
    no_group = engine.mask_value("cust-42", MaskingStrategy.HASH)
    grouped = engine.mask_value("cust-42", MaskingStrategy.HASH, consistency_group="customer_id")
    assert no_group != grouped, "group should change the HMAC salt"


def test_different_groups_yield_different_hashes():
    engine = MaskingEngine(salt="test-salt")
    a = engine.mask_value("cust-42", MaskingStrategy.HASH, consistency_group="g1")
    b = engine.mask_value("cust-42", MaskingStrategy.HASH, consistency_group="g2")
    assert a != b


def test_mask_row_applies_consistency_group_across_columns():
    engine = MaskingEngine(salt="s")
    row = {"primary_id": "abc", "secondary_id": "abc"}
    rules = [
        {"column_name": "primary_id", "masking_type": "hash", "consistency_group": "customer"},
        {"column_name": "secondary_id", "masking_type": "hash", "consistency_group": "customer"},
    ]
    masked = engine.mask_row(row, rules)
    assert masked["primary_id"] == masked["secondary_id"], (
        "matching inputs + shared group → equal masked output"
    )


def test_linked_columns_seed_faker_deterministically():
    """Two rows with identical linked values produce identical faker output."""
    engine = MaskingEngine(salt="s")
    rules = [
        {
            "column_name": "city",
            "masking_type": "faker_replace",
            "masking_config": {"provider": "city"},
            "linked_column_names": ["state"],
        }
    ]
    a = engine.mask_row({"city": "ignored", "state": "TX"}, rules)["city"]
    b = engine.mask_row({"city": "different", "state": "TX"}, rules)["city"]
    c = engine.mask_row({"city": "ignored", "state": "CA"}, rules)["city"]
    assert a == b, "same linked-column value → same faker output regardless of input"
    assert a != c, "different linked-column value → different faker output"


def test_mask_row_no_consistency_falls_back_to_global_salt():
    engine = MaskingEngine(salt="s")
    row = {"x": "v"}
    rules = [{"column_name": "x", "masking_type": "hash"}]
    masked = engine.mask_row(row, rules)
    assert masked["x"] == engine.mask_value("v", MaskingStrategy.HASH)
