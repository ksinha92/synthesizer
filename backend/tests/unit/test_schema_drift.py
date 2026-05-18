"""Unit tests for the schema-drift guard service."""

from __future__ import annotations

import pytest

from app.domain.connection.schema_drift import (
    SchemaDriftDetected,
    assert_no_drift,
    block_on_schema_change_enabled,
    fingerprint,
)


def _fp(schema: str, tables: dict[str, list[str]]):
    return fingerprint(schema, [(t, cols) for t, cols in tables.items()])


class TestFingerprint:
    def test_stable_across_table_order(self) -> None:
        a = _fp("public", {"users": ["id", "email"], "orders": ["id"]})
        b = _fp("public", {"orders": ["id"], "users": ["email", "id"]})
        assert a.digest == b.digest

    def test_changes_when_column_added(self) -> None:
        a = _fp("public", {"users": ["id"]})
        b = _fp("public", {"users": ["id", "email"]})
        assert a.digest != b.digest


class TestAssertNoDrift:
    def test_passes_when_identical(self) -> None:
        a = _fp("p", {"t": ["c"]})
        assert_no_drift(a, a)

    def test_raises_on_difference(self) -> None:
        a = _fp("p", {"t": ["c"]})
        b = _fp("p", {"t": ["c", "d"]})
        with pytest.raises(SchemaDriftDetected) as exc:
            assert_no_drift(a, b)
        assert exc.value.schema_name == "p"


class TestBlockOnSchemaChangeFlag:
    def test_disabled_by_default(self) -> None:
        assert block_on_schema_change_enabled(None) is False
        assert block_on_schema_change_enabled({}) is False

    def test_enabled_when_truthy(self) -> None:
        assert block_on_schema_change_enabled({"block_on_schema_change": True}) is True
