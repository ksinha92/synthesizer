"""Partition contract for masking_tasks rule dispatch.

Codex stop-time review caught a subtle regression: when the previous
dispatch flagged a table as "joint" because ONE rule had a
consistency_group, EVERY rule on the table was routed through mask_row.
That made an unrelated faker_replace rule's output suddenly dependent on
row identity — its behavior changed because of a sibling rule.

The contract these tests lock in:

- column-only strategies (SHUFFLE) → mask_column path, regardless.
- rules with consistency_group / linked_column_ids → mask_row path.
- everything else → mask_column path. Never coerced into mask_row just
  because a sibling rule is joint.
"""

from __future__ import annotations

from app.infrastructure.messaging.masking_tasks import partition_masking_rules


def _rule(name: str, masking_type: str, **extras) -> dict:
    return {"column_name": name, "masking_type": masking_type, **extras}


def test_shuffle_always_column_only():
    column_only, plain, joint = partition_masking_rules([
        _rule("a", "shuffle"),
    ])
    assert len(column_only) == 1 and column_only[0]["column_name"] == "a"
    assert plain == [] and joint == []


def test_shuffle_with_consistency_group_still_column_only():
    """Joint settings on a column-only strategy are meaningless — they must
    not promote the rule into the joint bucket."""
    column_only, plain, joint = partition_masking_rules([
        _rule("a", "shuffle", consistency_group="g"),
    ])
    assert column_only and column_only[0]["consistency_group"] == "g"
    assert joint == []


def test_consistency_group_routes_to_joint():
    _, plain, joint = partition_masking_rules([
        _rule("x", "hash", consistency_group="cust"),
    ])
    assert plain == []
    assert len(joint) == 1


def test_linked_column_ids_routes_to_joint():
    _, plain, joint = partition_masking_rules([
        _rule("city", "faker_replace", linked_column_ids=["abc"]),
    ])
    assert plain == []
    assert len(joint) == 1


def test_plain_rule_stays_plain_alongside_joint_sibling():
    """The regression case Codex caught: a faker_replace rule with no joint
    settings must NOT be coerced into mask_row just because another rule
    on the same table declares consistency_group."""
    column_only, plain, joint = partition_masking_rules([
        _rule("name", "faker_replace"),
        _rule("customer_id", "hash", consistency_group="cust"),
    ])
    assert len(plain) == 1 and plain[0]["column_name"] == "name"
    assert len(joint) == 1 and joint[0]["column_name"] == "customer_id"
    assert column_only == []


def test_three_way_split():
    column_only, plain, joint = partition_masking_rules([
        _rule("birth_state", "shuffle"),
        _rule("email", "faker_replace"),
        _rule("customer_id", "hash", consistency_group="cust"),
        _rule("city", "faker_replace", linked_column_ids=["abc"]),
    ])
    assert [r["column_name"] for r in column_only] == ["birth_state"]
    assert [r["column_name"] for r in plain] == ["email"]
    assert sorted(r["column_name"] for r in joint) == ["city", "customer_id"]
