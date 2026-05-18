"""Unit tests for connector changes that fix Database View parity.

These tests do NOT spin up real database connections — they verify the
metadata-shaping branches the Database View depends on:

- MongoDB: ``stats.mixed_types`` surfaces when a sampled field has
  multiple types so the UI can render a "mixed" badge.
- Redshift: ``_is_transient`` correctly classifies cold-start /
  warehouse-resume errors so cluster wake-ups don't fail discovery.
- Databricks: ``DESCRIBE TABLE`` output with ``NOT NULL`` in the type
  column resolves ``is_nullable=False`` (default had been hardcoded True).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# MongoDB mixed_types badge
# ──────────────────────────────────────────────────────────────────────


class _FakeCursor:
    """Async iterable that yields preset docs, matching motor's cursor API."""

    def __init__(self, docs: list[dict]) -> None:
        self._docs = list(docs)
        self._sampling = self

    def limit(self, _n: int) -> "_FakeCursor":
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


def _make_mongo_connector(docs: list[dict]):
    from app.infrastructure.connectors.nosql.mongodb import MongoDBConnector

    connector = MongoDBConnector(
        host="localhost",
        port=27017,
        database_name="test",
        username="",
        password="",
        extra_params={"max_sample_size": 50, "max_doc_depth": 2},
    )

    # Replace the motor client with a hand-rolled stub that returns our
    # fake cursor — no network, no event loop juggling.
    fake_db = MagicMock()
    fake_collection = MagicMock()
    fake_collection.find = MagicMock(return_value=_FakeCursor(docs))
    fake_db.__getitem__ = lambda _self, _k: fake_collection
    fake_client = MagicMock()
    fake_client.__getitem__ = lambda _self, _k: fake_db
    connector._client = fake_client
    return connector


@pytest.mark.asyncio
async def test_mongo_mixed_types_surface_via_stats():
    """A field with str + int values reports stats.mixed_types."""
    docs = [
        {"_id": 1, "age": 25, "city": "NYC"},
        {"_id": 2, "age": "thirty", "city": "LA"},
        {"_id": 3, "age": 35, "city": "SF"},
    ]
    connector = _make_mongo_connector(docs)
    cols = await connector.get_columns("test", "users")

    by_name = {c["name"]: c for c in cols}
    age = by_name["age"]
    assert "stats" in age, "mixed-type field must carry stats payload"
    assert set(age["stats"]["mixed_types"]) == {"varchar", "integer"}
    assert sum(age["stats"]["type_breakdown"].values()) == 3

    # City is monotyped — no mixed_types stash.
    city = by_name["city"]
    assert "stats" not in city or "mixed_types" not in (city.get("stats") or {})


@pytest.mark.asyncio
async def test_mongo_single_type_field_omits_stats():
    docs = [{"_id": i, "name": "Alice"} for i in range(3)]
    connector = _make_mongo_connector(docs)
    cols = await connector.get_columns("test", "users")
    name = next(c for c in cols if c["name"] == "name")
    assert name["data_type"] == "varchar"
    assert "stats" not in name or not name["stats"].get("mixed_types")


# ──────────────────────────────────────────────────────────────────────
# Redshift transient-error classifier
# ──────────────────────────────────────────────────────────────────────


def test_redshift_is_transient_recognises_sqlstate_codes():
    from app.infrastructure.connectors.cloud.redshift import _is_transient

    class _Exc(Exception):
        def __init__(self, msg: str, sqlstate: str | None = None) -> None:
            super().__init__(msg)
            self.sqlstate = sqlstate

    assert _is_transient(_Exc("boom", sqlstate="08001"))
    assert _is_transient(_Exc("boom", sqlstate="08006"))
    # Generic message-based detection (drivers that drop sqlstate entirely).
    assert _is_transient(_Exc("the cluster is restarting"))
    assert _is_transient(_Exc("cluster is resuming after pause"))
    # Non-connection errors stay non-transient.
    assert not _is_transient(_Exc("permission denied", sqlstate="42501"))
    assert not _is_transient(_Exc("syntax error"))


# ──────────────────────────────────────────────────────────────────────
# Databricks NOT NULL parsing
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_databricks_is_nullable_parsed_from_describe():
    """DESCRIBE TABLE row with NOT NULL in the type column → is_nullable=False.

    Prior behavior hardcoded ``is_nullable=True`` for every column, which
    silently hid a real schema constraint and weakened the Database View's
    "Sensitivity" filter (NOT NULL columns are higher signal for PII review).
    """
    from app.infrastructure.connectors.cloud import databricks as dbx

    # DESCRIBE returns 3-tuple rows: (column_name, data_type, comment).
    rows: list[tuple[str, str, str]] = [
        ("id", "BIGINT NOT NULL", ""),
        ("email", "STRING", ""),
        ("name", "STRING", "NOT NULL"),  # NOT NULL hint in comment slot.
        ("", "", ""),  # blank terminator
        ("# Partition Information", "", ""),
    ]

    class _Cursor:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def execute(self, sql: str, *_: Any) -> None:
            self.queries.append(sql)

        def fetchall(self) -> list[tuple[str, str, str]]:
            # SHOW TABLES validation path → return target table once.
            if any("SHOW TABLES" in q for q in self.queries):
                # Return only on the validation call; next fetch is DESCRIBE.
                self.queries = []
                return [("test_db", "users", False)]
            return rows

        def close(self) -> None:
            pass

    class _Conn:
        def cursor(self) -> _Cursor:
            return _Cursor()

    connector = dbx.DatabricksConnector(
        host="example.databricks.com",
        port=443,
        database_name="test_catalog",
        username="",
        password="",
        extra_params={"http_path": "/sql/1.0/warehouses/x", "access_token": "token"},
    )
    connector._conn = _Conn()
    # Replace executor with inline runner so we don't depend on threading.
    async def _run_inline(fn, *args):
        return fn(*args)

    connector._run = _run_inline  # type: ignore[assignment]

    cols = await connector.get_columns("test_db", "users")
    by_name = {c["name"]: c for c in cols}
    assert by_name["id"]["is_nullable"] is False
    assert by_name["email"]["is_nullable"] is True
    assert by_name["name"]["is_nullable"] is False
