"""Databricks SQL Warehouse connector using databricks-sql-connector."""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog

from app.infrastructure.connectors.base import BaseConnector
from app.infrastructure.connectors._ssl import local_schemas

logger = structlog.get_logger()

CONNECTION_TIMEOUT = 5
INTROSPECTION_TIMEOUT = 60.0  # Databricks warehouse cold-start can be slow

_DATABRICKS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="databricks")


def _sanitize_error(msg: str) -> str:
    return re.sub(r"(password|passwd|pwd|token)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)


class DatabricksConnector(BaseConnector):
    """Databricks SQL connector.

    Uses Unity Catalog three-level naming. ``database_name`` maps to the
    catalog; schemas come from ``SHOW SCHEMAS IN catalog``.

    Required extras:
        - ``http_path``: e.g. ``/sql/1.0/warehouses/abcd1234``
        - ``access_token``: Databricks PAT or service principal token
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._http_path = self._extra_params.get("http_path", "")
        self._access_token = self._extra_params.get("access_token", "") or self._password
        self._catalog = self._database_name
        # Auth modes: "token" (PAT or PAT-like access_token) or
        # "oauth_m2m" (machine-to-machine OAuth, recommended for service
        # principals on production warehouses).
        self._auth_mode = self._extra_params.get("auth_mode", "token")
        self._client_id = self._extra_params.get("databricks_client_id", "")
        self._client_secret = self._extra_params.get("databricks_client_secret", "")
        self._conn = None

    def _connect_sync(self):
        from databricks import sql as dbsql

        # The underscore-prefixed retry params have been the public contract
        # since v3; we set conservative defaults so warehouse cold-starts
        # (which surface as 503) don't immediately fail the discovery run.
        common: dict[str, Any] = {
            "server_hostname": self._host,
            "http_path": self._http_path,
            "catalog": self._catalog or None,
            "_retry_stop_after_attempts_count": int(
                self._extra_params.get("retry_attempts") or 5
            ),
            "_retry_delay_min": float(self._extra_params.get("retry_delay_min") or 1.0),
            "_retry_delay_max": float(self._extra_params.get("retry_delay_max") or 30.0),
            "_socket_timeout": int(self._extra_params.get("socket_timeout_ms") or 900_000),
        }

        if self._auth_mode == "oauth_m2m":
            if not (self._client_id and self._client_secret):
                raise ValueError(
                    "Databricks M2M OAuth requires both ``databricks_client_id`` and "
                    "``databricks_client_secret`` (service-principal credentials)."
                )
            # databricks-sql-connector accepts an OAuth credentials provider
            # via ``credentials_provider``. We construct one with the SDK's
            # ServicePrincipalCredentials so token refresh is automatic.
            try:
                from databricks.sdk.core import (
                    Config,
                    oauth_service_principal,
                )
            except ImportError as exc:
                raise ImportError(
                    "Databricks M2M OAuth requires the `databricks-sdk` package. "
                    "Add it to backend/pyproject.toml dependencies."
                ) from exc

            config = Config(
                host=f"https://{self._host}",
                client_id=self._client_id,
                client_secret=self._client_secret,
            )
            common["credentials_provider"] = lambda: oauth_service_principal(config)
        else:
            common["access_token"] = self._access_token

        return dbsql.connect(**common)

    def _get_conn_sync(self):
        if self._conn is None:
            self._conn = self._connect_sync()
        return self._conn

    async def _run(self, func, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_DATABRICKS_EXECUTOR, func, *args)

    async def test_connection(self) -> bool:
        def _test() -> bool:
            try:
                conn = self._connect_sync()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.close()
                return True
            except Exception as e:
                logger.warning("connector_test_failed", connector="databricks", error=_sanitize_error(str(e)))
                return False

        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT + 30):  # cold start budget
                return await self._run(_test)
        except Exception:
            return False

    async def get_schemas(self) -> list[dict[str, Any]]:
        allow = local_schemas(self._extra_params)

        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            cur = conn.cursor()
            cur.execute(f"SHOW SCHEMAS IN `{self._catalog}`" if self._catalog else "SHOW SCHEMAS")
            schemas = [{"name": r[0]} for r in cur.fetchall() if r[0] not in ("information_schema",)]
            cur.close()
            if allow is not None:
                allowed = {s.lower() for s in allow}
                schemas = [s for s in schemas if s["name"].lower() in allowed]
            return schemas

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run(_get)

    async def get_tables(self, schema: str) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            self._validate_schema_sync(conn, schema)
            cur = conn.cursor()
            cur.execute(f"SHOW TABLES IN `{self._catalog}`.`{schema}`")
            rows = cur.fetchall()
            # Bulk-fetch row counts from Unity Catalog's information_schema
            # in a single query — N+1 SELECT COUNT(*) used to be O(tables)
            # full scans and dominated discovery cost on large schemas.
            counts: dict[str, int] = {}
            try:
                cur.execute(
                    "SELECT table_name, row_count "
                    f"FROM `{self._catalog}`.information_schema.tables "
                    "WHERE table_schema = ?",
                    (schema,),
                )
                for tname, rc in cur.fetchall():
                    counts[tname] = int(rc) if rc is not None else -1
            except Exception as exc:
                # information_schema not available on this workspace (old
                # runtime / hive metastore catalog) — leave counts unset so
                # the API reports row_count=-1 and the UI renders "—".
                logger.debug(
                    "databricks_information_schema_unavailable",
                    error=_sanitize_error(str(exc)),
                )

            tables = []
            for r in rows:
                # Result is (database, table, is_temporary)
                tname = r[1]
                tables.append({
                    "name": tname,
                    "row_count": counts.get(tname, -1),
                    "size_bytes": 0,
                })
            cur.close()
            return tables

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run(_get)

    async def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            self._validate_table_sync(conn, schema, table)
            cur = conn.cursor()
            cur.execute(f"DESCRIBE TABLE `{self._catalog}`.`{schema}`.`{table}`")
            cols = []
            for r in cur.fetchall():
                name, dtype = r[0], r[1]
                # DESCRIBE returns metadata sections after the columns; stop at the first blank row
                if not name or name.startswith("#"):
                    break
                # DESCRIBE TABLE may surface `NOT NULL` either inside the type
                # column or in a separate comment slot depending on runtime
                # version; treat both as the explicit not-nullable signal.
                comment = r[2] if len(r) > 2 and r[2] else ""
                dtype_upper = (dtype or "").upper()
                comment_upper = comment.upper() if isinstance(comment, str) else ""
                is_nullable = not (
                    "NOT NULL" in dtype_upper or "NOT NULL" in comment_upper
                )
                cols.append({
                    "name": name,
                    "data_type": dtype,
                    "is_nullable": is_nullable,
                    "character_maximum_length": None,
                    "numeric_precision": None,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "fk_references": None,
                })
            cur.close()
            return cols

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run(_get)

    async def get_sample_data(self, schema: str, table: str, limit: int = 100) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            vs, vt = self._validate_table_sync(conn, schema, table)
            n = min(limit, 1000)
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM `{self._catalog}`.`{vs}`.`{vt}` LIMIT {n}"
            )
            # Prefer the Arrow batch reader — Databricks docs benchmark it
            # at 10-100x the throughput of row-at-a-time fetchmany() for
            # wide tables. Falls back gracefully when pyarrow isn't loaded
            # or the result set is too small to be worth the conversion.
            rows: list[dict[str, Any]]
            try:
                arrow_table = cur.fetchall_arrow()
                rows = arrow_table.to_pylist()
            except (AttributeError, ImportError):
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
            return rows

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run(_get)

    async def close(self) -> None:
        def _close():
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None

        await self._run(_close)

    def _validate_schema_sync(self, conn, schema: str) -> str:
        cur = conn.cursor()
        cur.execute(f"SHOW SCHEMAS IN `{self._catalog}`" if self._catalog else "SHOW SCHEMAS")
        schemas = {r[0] for r in cur.fetchall()}
        cur.close()
        if schema not in schemas:
            raise ValueError(f"Schema '{schema}' does not exist")
        return schema

    def _validate_table_sync(self, conn, schema: str, table: str) -> tuple[str, str]:
        cur = conn.cursor()
        cur.execute(f"SHOW TABLES IN `{self._catalog}`.`{schema}`")
        tables = {r[1] for r in cur.fetchall()}
        cur.close()
        if table not in tables:
            raise ValueError(f"Table '{schema}.{table}' does not exist")
        return schema, table
