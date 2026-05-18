"""Profile-guided FakerEngine integration tests."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.synthetic.entities import SyntheticConfig
from app.infrastructure.engine.distribution_profiler import ColumnProfile
from app.infrastructure.engine.faker_engine import FakerEngine


def _config(table_name: str, columns: list[dict], row_count: int = 100) -> SyntheticConfig:
    return SyntheticConfig(
        name="t",
        tables=[{"table_name": table_name, "columns": columns, "row_count": row_count}],
        row_count=row_count,
    )


def test_numeric_profile_constrains_range():
    engine = FakerEngine(seed=42)
    profile = ColumnProfile(
        column_name="x", dtype="numeric",
        minimum=10, maximum=20, mean=15, std=3, cardinality=11,
    )
    config = _config("t", [{"column_name": "x", "data_type": "integer"}], row_count=100)
    result = asyncio.run(engine.generate(config, {"column_profiles": {"x": profile}}))
    values = [row["x"] for row in result["t"]]
    assert all(10 <= v <= 20 for v in values), f"out-of-range values: {[v for v in values if v < 10 or v > 20]}"


def test_categorical_profile_uses_learned_set():
    engine = FakerEngine(seed=42)
    profile = ColumnProfile(
        column_name="y", dtype="categorical",
        cardinality=2, frequencies={"A": 3, "B": 7},
    )
    config = _config("t", [{"column_name": "y", "data_type": "varchar"}], row_count=200)
    result = asyncio.run(engine.generate(config, {"column_profiles": {"y": profile}}))
    values = [row["y"] for row in result["t"]]
    assert set(values).issubset({"A", "B"}), f"unexpected values: {set(values) - {'A','B'}}"
    # Loose proportion check: B should dominate (~70%) given seed-stable Faker.
    assert values.count("B") > values.count("A")


def test_null_rate_honored():
    engine = FakerEngine(seed=42)
    profile = ColumnProfile(
        column_name="z", dtype="numeric",
        minimum=0, maximum=100, mean=50, std=20, cardinality=100,
        null_rate=0.3,
    )
    config = _config(
        "t",
        [{"column_name": "z", "data_type": "integer", "is_nullable": True}],
        row_count=200,
    )
    result = asyncio.run(engine.generate(config, {"column_profiles": {"z": profile}}))
    values = [row["z"] for row in result["t"]]
    null_fraction = sum(1 for v in values if v is None) / len(values)
    assert 0.18 <= null_fraction <= 0.42, f"null_fraction={null_fraction} outside tolerance"


def test_no_profile_falls_back_to_pii_or_type():
    """Regression: when no profile is supplied, existing PII / type behavior unchanged."""
    engine = FakerEngine(seed=42)
    config = _config(
        "t",
        [
            {"column_name": "email", "data_type": "varchar", "pii_type": "email"},
            {"column_name": "id", "data_type": "integer"},
        ],
        row_count=10,
    )
    result = asyncio.run(engine.generate(config, {}))
    rows = result["t"]
    assert len(rows) == 10
    assert all("@" in row["email"] for row in rows)
    assert all(isinstance(row["id"], int) for row in rows)
