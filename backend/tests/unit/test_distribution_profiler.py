"""Unit tests for DistributionProfiler."""

from __future__ import annotations

import pandas as pd

from app.infrastructure.engine.distribution_profiler import (
    ColumnProfile,
    DistributionProfiler,
)


def test_profile_numeric_column():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
    profiles = DistributionProfiler().profile_dataframe(df)
    p = profiles["x"]
    assert p.dtype == "numeric"
    assert p.minimum == 1
    assert p.maximum == 5
    assert p.mean == 3
    assert p.cardinality == 5


def test_profile_categorical_column():
    df = pd.DataFrame({"y": ["A", "A", "B", "B", "B"]})
    profiles = DistributionProfiler().profile_dataframe(df)
    p = profiles["y"]
    assert p.dtype == "categorical"
    assert p.frequencies == {"A": 2, "B": 3}
    assert p.cardinality == 2


def test_profile_string_pattern_detected():
    df = pd.DataFrame({
        "ref": [f"POL-{i:04d}-XX" for i in range(60)]  # 60 unique → not categorical
    })
    profiles = DistributionProfiler().profile_dataframe(df)
    p = profiles["ref"]
    assert p.dtype == "string"
    assert p.pattern_hint == r"[A-Za-z]+\-\d+\-[A-Za-z]+"


def test_profile_null_rate():
    df = pd.DataFrame({"z": [1, None, 3, None, 5]})
    p = DistributionProfiler().profile_dataframe(df)["z"]
    assert p.dtype == "numeric"
    assert p.null_rate == 0.4


def test_profile_empty_column():
    df = pd.DataFrame({"empty": [None, None, None]})
    p = DistributionProfiler().profile_dataframe(df)["empty"]
    assert p.dtype == "empty"
    assert p.null_rate == 1.0


def test_profile_sample_values():
    df = pd.DataFrame({"x": [10, 20, 30, 40, 50, 60, 70]})
    p = DistributionProfiler().profile_dataframe(df)["x"]
    assert p.sample_values == [10, 20, 30, 40, 50]
