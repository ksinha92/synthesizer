"""Tests for FileSetOrchestrator."""

from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from app.domain.synthetic.file_schema import (
    CrossFileFK,
    FileFieldDefinition,
    FileSchemaDefinition,
    FileSetDefinition,
)
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.engine.file_set_orchestrator import FileSetOrchestrator
from app.infrastructure.parsers.sample_file_parser import parse_csv


def _customers_schema() -> FileSchemaDefinition:
    return FileSchemaDefinition(
        name="customers",
        fields=[
            FileFieldDefinition(name="id", data_type="alphanumeric", length=36, byte_length=36, start_position=0),
            FileFieldDefinition(name="name", data_type="alphanumeric", length=30, byte_length=30, start_position=36),
        ],
        file_format=FileFormat.CSV.value,
    )


def _orders_schema() -> FileSchemaDefinition:
    return FileSchemaDefinition(
        name="orders",
        fields=[
            FileFieldDefinition(name="order_id", data_type="alphanumeric", length=36, byte_length=36, start_position=0),
            FileFieldDefinition(
                name="customer_id", data_type="alphanumeric", length=36, byte_length=36,
                start_position=36, fk_reference=("customers", "id"),
            ),
        ],
        file_format=FileFormat.CSV.value,
    )


def test_plan_topo_sorts_by_fk():
    file_set = FileSetDefinition(
        name="set",
        schemas=[_orders_schema(), _customers_schema()],
        foreign_keys=[CrossFileFK("orders", "customer_id", "customers", "id")],
    )
    orch = FileSetOrchestrator(file_set)
    assert orch.plan() == ["customers", "orders"]


def test_plan_detects_cycle():
    a = FileSchemaDefinition(
        name="A",
        fields=[FileFieldDefinition(name="a_id", data_type="alphanumeric", length=4, byte_length=4, start_position=0)],
        file_format=FileFormat.CSV.value,
    )
    b = FileSchemaDefinition(
        name="B",
        fields=[FileFieldDefinition(name="b_id", data_type="alphanumeric", length=4, byte_length=4, start_position=0)],
        file_format=FileFormat.CSV.value,
    )
    file_set = FileSetDefinition(
        name="cyclic",
        schemas=[a, b],
        foreign_keys=[
            CrossFileFK("A", "a_id", "B", "b_id"),
            CrossFileFK("B", "b_id", "A", "a_id"),
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        FileSetOrchestrator(file_set).plan()


def test_generate_parent_child_fk_integrity(tmp_path):
    file_set = FileSetDefinition(
        name="biz",
        schemas=[_customers_schema(), _orders_schema()],
        foreign_keys=[CrossFileFK("orders", "customer_id", "customers", "id")],
    )
    orch = FileSetOrchestrator(file_set, row_counts={"customers": 10, "orders": 25}, seed=42)
    written = asyncio.run(orch.generate(tmp_path))

    assert len(written) == 2
    cust_path = next(p for p in written if "customers" in p.name)
    ord_path = next(p for p in written if "orders" in p.name)

    cust_df = parse_csv(cust_path, _customers_schema())
    ord_df = parse_csv(ord_path, _orders_schema())

    cust_ids = set(cust_df["id"].astype(str).tolist())
    ord_fks = set(ord_df["customer_id"].astype(str).tolist())
    # Every order FK must come from the customer pool.
    assert ord_fks.issubset(cust_ids), f"orphan FKs: {ord_fks - cust_ids}"


def test_generate_mixed_format(tmp_path):
    """Parent CSV + child Parquet — both written, both valid."""
    customers = _customers_schema()
    orders = _orders_schema()
    orders.file_format = FileFormat.PARQUET.value

    file_set = FileSetDefinition(
        name="mixed",
        schemas=[customers, orders],
        foreign_keys=[CrossFileFK("orders", "customer_id", "customers", "id")],
    )
    orch = FileSetOrchestrator(file_set, row_counts={"customers": 3, "orders": 5}, seed=1)
    written = asyncio.run(orch.generate(tmp_path))
    assert any(p.suffix == ".csv" for p in written)
    assert any(p.suffix == ".parquet" for p in written)


class TestFileSetValidationCatchesBadFKs:
    """Codex P2 (synthetic.py:1002): the API now runs ``validate()`` after
    ``from_dict()`` so cross-file FK typos are rejected before the worker
    silently generates the column as random data. These tests lock that
    contract in at the domain level so the API can keep trusting it."""

    def test_clean_definition_validates(self):
        file_set = FileSetDefinition(
            name="ok",
            schemas=[_customers_schema(), _orders_schema()],
            foreign_keys=[CrossFileFK("orders", "customer_id", "customers", "id")],
        )
        assert file_set.validate() == []

    def test_unknown_source_file_reported(self):
        file_set = FileSetDefinition(
            name="bad-source",
            schemas=[_customers_schema(), _orders_schema()],
            foreign_keys=[CrossFileFK("typo_orders", "customer_id", "customers", "id")],
        )
        errors = file_set.validate()
        assert any("typo_orders" in e for e in errors)

    def test_unknown_target_field_reported(self):
        file_set = FileSetDefinition(
            name="bad-target-field",
            schemas=[_customers_schema(), _orders_schema()],
            foreign_keys=[CrossFileFK("orders", "customer_id", "customers", "uuid_typo")],
        )
        errors = file_set.validate()
        assert any("uuid_typo" in e for e in errors)

    def test_duplicate_schema_names_reported(self):
        file_set = FileSetDefinition(
            name="dup-schemas",
            schemas=[_customers_schema(), _customers_schema()],
        )
        errors = file_set.validate()
        assert any("Duplicate" in e and "customers" in e for e in errors)
