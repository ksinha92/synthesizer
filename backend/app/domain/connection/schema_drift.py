"""Schema-drift detection for connections with ``block_on_schema_change`` set.

Comparison strategy is intentionally cheap — count + name hash of tables in
each schema. A real diff is available via ``/projects/{id}/discovery/diff``;
this guard is for the synchronous job-start path where we want sub-second
feedback before kicking off a long-running mask or subset.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SchemaFingerprint:
    """Deterministic summary of a schema's structural shape."""

    schema_name: str
    table_count: int
    column_count: int
    digest: str  # SHA256 of "schema.table.column|..." sorted


def fingerprint(schema_name: str, tables_with_columns: Iterable[tuple[str, Iterable[str]]]) -> SchemaFingerprint:
    """Build a fingerprint from tuples of ``(table_name, [column_names...])``."""
    pairs: list[str] = []
    table_count = 0
    column_count = 0
    for table_name, columns in tables_with_columns:
        table_count += 1
        cols = sorted(columns)
        column_count += len(cols)
        for col in cols:
            pairs.append(f"{schema_name}.{table_name}.{col}")
    digest = hashlib.sha256("|".join(sorted(pairs)).encode()).hexdigest()
    return SchemaFingerprint(
        schema_name=schema_name,
        table_count=table_count,
        column_count=column_count,
        digest=digest,
    )


class SchemaDriftDetected(Exception):
    """Raised when a live fingerprint differs from the persisted snapshot."""

    def __init__(self, schema_name: str, before: str, after: str) -> None:
        super().__init__(
            f"Schema '{schema_name}' has changed since last discovery snapshot "
            f"(before={before[:12]}…, after={after[:12]}…)"
        )
        self.schema_name = schema_name
        self.before = before
        self.after = after


def assert_no_drift(persisted: SchemaFingerprint, live: SchemaFingerprint) -> None:
    """Raise ``SchemaDriftDetected`` if the two fingerprints disagree."""
    if persisted.digest != live.digest:
        raise SchemaDriftDetected(persisted.schema_name, persisted.digest, live.digest)


def block_on_schema_change_enabled(extra_params: dict | None) -> bool:
    """Read the UI's ``block_on_schema_change`` toggle out of extra_params."""
    return bool((extra_params or {}).get("block_on_schema_change"))
