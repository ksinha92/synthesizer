"""Phase 59 F11 — ``quality_check`` node type is gone.

The legacy ``quality_check`` workflow node was never wired to anything
useful — it logged a line and moved on. Removing it (a) makes the
validator's edge rules simpler, (b) lets ``_execute_node`` fail fast on
truly unknown types, and (c) keeps the React palette from offering a
dead-end node. These tests pin all three.
"""

from __future__ import annotations

from app.domain.workflow.services import (
    EDGE_RULES,
    NODE_TYPE_ALIASES,
    VALID_NODE_TYPES,
    WorkflowValidator,
)


def test_quality_check_not_in_valid_node_types() -> None:
    assert "quality_check" not in VALID_NODE_TYPES


def test_export_alias_no_longer_canonicalizes_to_quality_check() -> None:
    # ``export`` was an alias for ``quality_check`` in earlier rounds.
    # Both go away together so legacy DAGs surface a clear validation
    # error rather than silently mapping onto the now-removed type.
    assert "export" not in NODE_TYPE_ALIASES


def test_edge_rules_drop_quality_check() -> None:
    # No source can target quality_check, and quality_check is no longer
    # a source entry at all.
    assert "quality_check" not in EDGE_RULES
    for src_type, allowed in EDGE_RULES.items():
        assert "quality_check" not in allowed, (
            f"EDGE_RULES[{src_type!r}] still allows quality_check"
        )


def test_validator_rejects_quality_check_node() -> None:
    dag = {
        "nodes": [
            {"id": "n1", "type": "discovery"},
            {"id": "n2", "type": "quality_check"},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    errors = WorkflowValidator.validate_dag(dag)
    assert errors
    assert any("quality_check" in e for e in errors)


def test_validator_still_accepts_canonical_types() -> None:
    dag = {
        "nodes": [
            {"id": "n1", "type": "discovery"},
            {"id": "n2", "type": "masking"},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    errors = WorkflowValidator.validate_dag(dag)
    assert errors == []
