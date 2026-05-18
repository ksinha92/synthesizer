"""Distribution profiler — turn a sample DataFrame into per-column profiles.

Profiles feed `FakerEngine.generate(..., schema_metadata={"column_profiles": ...})`
so generated data matches the sample's shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd


CATEGORICAL_THRESHOLD = 50  # cardinality below this → categorical, otherwise free-form
PATTERN_SAMPLE_SIZE = 20


@dataclass
class ColumnProfile:
    """Summary of one column's distribution."""

    column_name: str
    dtype: Literal["numeric", "categorical", "string", "empty"]
    null_rate: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    std: float | None = None
    cardinality: int = 0
    frequencies: dict[str, int] | None = None
    pattern_hint: str | None = None
    sample_values: list = field(default_factory=list)


def _simplify_to_pattern(value: str) -> str:
    """Collapse digit runs to \\d+ and letter runs to [A-Za-z]+ (preserve other chars)."""
    result = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch.isdigit():
            while i < len(value) and value[i].isdigit():
                i += 1
            result.append(r"\d+")
        elif ch.isalpha():
            while i < len(value) and value[i].isalpha():
                i += 1
            result.append(r"[A-Za-z]+")
        else:
            result.append(re.escape(ch))
            i += 1
    return "".join(result)


class DistributionProfiler:
    """Profile each column of a DataFrame."""

    def profile_dataframe(self, df: pd.DataFrame) -> dict[str, ColumnProfile]:
        return {col: self._profile_column(df[col], col) for col in df.columns}

    def _profile_column(self, series: pd.Series, name: str) -> ColumnProfile:
        non_null = series.dropna()
        total = len(series)
        null_rate = float((total - len(non_null)) / total) if total else 0.0

        if non_null.empty:
            return ColumnProfile(column_name=name, dtype="empty", null_rate=null_rate)

        sample_values = non_null.head(5).tolist()

        if pd.api.types.is_numeric_dtype(non_null):
            return ColumnProfile(
                column_name=name,
                dtype="numeric",
                null_rate=null_rate,
                minimum=float(non_null.min()),
                maximum=float(non_null.max()),
                mean=float(non_null.mean()),
                std=float(non_null.std()) if len(non_null) > 1 else 0.0,
                cardinality=int(non_null.nunique()),
                sample_values=sample_values,
            )

        # Cast to strings for categorical / pattern inference.
        as_str = non_null.astype(str)
        cardinality = int(as_str.nunique())

        if cardinality < CATEGORICAL_THRESHOLD:
            freqs = as_str.value_counts().to_dict()
            return ColumnProfile(
                column_name=name,
                dtype="categorical",
                null_rate=null_rate,
                cardinality=cardinality,
                frequencies={str(k): int(v) for k, v in freqs.items()},
                sample_values=sample_values,
            )

        pattern_hint = self._detect_pattern(as_str)
        return ColumnProfile(
            column_name=name,
            dtype="string",
            null_rate=null_rate,
            cardinality=cardinality,
            pattern_hint=pattern_hint,
            sample_values=sample_values,
        )

    def _detect_pattern(self, series: pd.Series) -> str | None:
        sample = series.head(PATTERN_SAMPLE_SIZE)
        if sample.empty:
            return None
        patterns = sample.apply(_simplify_to_pattern)
        unique = patterns.unique()
        if len(unique) == 1:
            return str(unique[0])
        return None
