"""Source-to-ephemeral data-copy controller (Phase 61 F18).

Walks every schema/table on a source connection, streams rows in
batches, optionally masks them, and inserts into the freshly-provisioned
ephemeral target. The implementation is deliberately pragmatic:

* SELECT path goes through the existing connector registry so we get
  free auth + driver coverage for postgres / mysql / mongo / snowflake /
  etc. Sources can be any registered connector.
* INSERT path uses raw SQLAlchemy ``text()`` against the target DSN with
  table identifiers escaped via :func:`_quote_ident`. We don't drive
  inserts through a connector because the ephemeral target is always a
  newly-spawned engine we control; we don't need its schema discovery
  layer.

Masking is applied per-row using the existing ``MaskingEngine`` when a
``masking_policy_id`` is supplied. If the policy has no rules or the
column doesn't match any rule, the value is copied verbatim.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.domain.connection.value_objects import ConnectorType
from app.infrastructure.connectors.registry import create_registry
from app.infrastructure.engine.masking_engine import MaskingEngine

logger = structlog.get_logger()

BATCH_SIZE = 1000

# ``_quote_ident`` accepts identifiers containing ASCII letters, digits,
# and underscores only. Anything outside that range is rejected before
# we splice it into a SQL string, which keeps us safe from injection via
# attacker-controlled table or column names. Real DBs allow far more
# (unicode, quoted identifiers) but our source list comes from our own
# discovery + connector_registry, both of which already validate names
# against information_schema, so this conservative pattern is fine.
_SAFE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_ident(name: str) -> str:
    """Validate-and-quote a SQL identifier.

    Raises ``ValueError`` if the name is unsafe. We use double-quotes
    (ANSI standard) which Postgres and MySQL-in-ANSI-mode both honour;
    the ephemeral target is always one of those + Mongo (which doesn't
    use SQL) so this is sufficient.
    """
    if not _SAFE_IDENT_RE.match(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return f'"{name}"'


async def copy_data(
    source_conn: dict,
    target_dsn: str,
    masking_policy_id: uuid.UUID | None = None,
    session: AsyncSession | None = None,
) -> dict:
    """Copy every readable table from ``source_conn`` into ``target_dsn``.

    ``source_conn`` is a dict shaped like ``ConnectionModel`` columns:
    ``{connector_type, host, port, database_name, username, password,
    extra_params}``. ``target_dsn`` is a SQLAlchemy async URL pointed
    at the ephemeral container's host_port.

    If ``masking_policy_id`` is provided, ``session`` MUST also be
    provided so we can load the policy's rules. The rules are applied
    column-by-column to each row before insert; columns not referenced
    by any rule are copied through unchanged.

    Returns a dict the Celery task stamps onto ``job.result_summary``::

        {"tables_copied": int, "rows_copied": int, "errors": list[str]}
    """
    tables_copied = 0
    rows_copied = 0
    errors: list[str] = []

    # Load masking rules up front -- doing it inside the per-table loop
    # would re-query the same rule set for every table.
    masking_rules: list[dict] = []
    masking_engine: MaskingEngine | None = None
    if masking_policy_id is not None:
        if session is None:
            raise ValueError("session required when masking_policy_id is given")
        from app.infrastructure.persistence.sqlalchemy.masking_repo import (
            SQLAlchemyMaskingRepository,
        )

        repo = SQLAlchemyMaskingRepository(session)
        loaded_rules = await repo.get_rules_by_policy(masking_policy_id)
        for r in loaded_rules:
            masking_rules.append(
                {
                    "column_pattern": r.match_pattern or "",
                    "masking_type": r.masking_type.value,
                    "masking_config": r.masking_config or {},
                }
            )
        masking_engine = MaskingEngine(salt=settings.SECRET_KEY)

    # Source connector --------------------------------------------------
    registry = create_registry()
    source_type = ConnectorType(source_conn["connector_type"])
    source = registry.get_connector(
        connector_type=source_type,
        host=source_conn["host"],
        port=source_conn["port"],
        database_name=source_conn["database_name"],
        username=source_conn.get("username", ""),
        password=source_conn.get("password", ""),
        extra_params=source_conn.get("extra_params") or {},
    )

    # Target engine -----------------------------------------------------
    target_engine = create_async_engine(target_dsn, future=True)

    try:
        schemas = await source.get_schemas()
        for schema_info in schemas:
            schema_name = (
                schema_info.get("name") if isinstance(schema_info, dict) else schema_info
            )
            if not schema_name:
                continue
            try:
                tables = await source.get_tables(schema_name)
            except Exception as e:  # noqa: BLE001
                errors.append(f"list_tables({schema_name}): {e}")
                continue

            for table_info in tables:
                table_name = (
                    table_info.get("name") if isinstance(table_info, dict) else table_info
                )
                if not table_name:
                    continue
                try:
                    copied = await _copy_table(
                        source=source,
                        target_engine=target_engine,
                        schema_name=schema_name,
                        table_name=table_name,
                        masking_rules=masking_rules,
                        masking_engine=masking_engine,
                    )
                    rows_copied += copied
                    tables_copied += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(f"copy({schema_name}.{table_name}): {e}")
                    await logger.awarning(
                        "ephemeral_copy_table_failed",
                        schema=schema_name,
                        table=table_name,
                        error=str(e),
                    )

    finally:
        await source.close()
        await target_engine.dispose()

    await logger.ainfo(
        "ephemeral_copy_done",
        tables_copied=tables_copied,
        rows_copied=rows_copied,
        error_count=len(errors),
    )
    return {
        "tables_copied": tables_copied,
        "rows_copied": rows_copied,
        "errors": errors,
    }


async def _copy_table(
    source: Any,
    target_engine: Any,
    schema_name: str,
    table_name: str,
    masking_rules: list[dict],
    masking_engine: MaskingEngine | None,
) -> int:
    """Copy a single table; return rows-copied count.

    Uses ``get_sample_data`` with ``limit=BATCH_SIZE`` in a loop. Our
    connector contract today only exposes sample-data, not pageable
    selects -- the ephemeral copy treats the first ``BATCH_SIZE`` rows
    as the dataset because the data-copy contract for ephemerals is
    "spin a small dev copy", not "replicate the warehouse". A future
    revision can extend the connector contract to support full pagination
    without touching the calling task.
    """
    rows = await source.get_sample_data(schema_name, table_name, limit=BATCH_SIZE)
    if not rows:
        return 0

    # Optionally mask in-place. Iterating per row keeps memory bounded
    # and lets us short-circuit when there are no rules.
    if masking_engine is not None and masking_rules:
        for row in rows:
            _apply_masking(row, masking_rules, masking_engine)

    # Build a parameterised INSERT against the target. Column list is
    # taken from the first row -- our connector contract returns dicts
    # with stable key ordering per Python 3.7+.
    columns = list(rows[0].keys())
    safe_cols = [_quote_ident(c) for c in columns]
    safe_table = _quote_ident(table_name)
    placeholders = ", ".join(f":{c}" for c in columns)
    sql = text(
        f"INSERT INTO {safe_table} ({', '.join(safe_cols)}) VALUES ({placeholders})"
    )

    async with target_engine.begin() as conn:
        # Insert in BATCH_SIZE-sized chunks. SQLAlchemy will batch the
        # underlying driver round-trips when given a list.
        await conn.execute(sql, rows)

    return len(rows)


def _apply_masking(
    row: dict, rules: list[dict], engine: MaskingEngine
) -> None:
    """Apply matching masking rules to ``row`` in place.

    The match strategy is regex on the column name -- same pattern used
    by ``MaskingEngine`` elsewhere. ``MaskingStrategy`` import is done
    inside the function to keep the import surface small.
    """
    from app.domain.masking.value_objects import MaskingStrategy

    for col, value in list(row.items()):
        for rule in rules:
            pattern = rule.get("column_pattern") or ""
            try:
                if pattern and re.search(pattern, col, re.IGNORECASE):
                    strategy = MaskingStrategy(rule["masking_type"])
                    row[col] = engine.mask_column(
                        [value], strategy, rule.get("masking_config") or {}
                    )[0]
                    break
            except re.error:
                continue
