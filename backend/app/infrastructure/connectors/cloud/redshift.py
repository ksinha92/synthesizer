"""Amazon Redshift connector using redshift_connector (sync, wrapped in executor).

Redshift speaks the Postgres wire protocol but the catalog SQL diverges enough
(``svv_table_info``, ``pg_table_def`` etc.) that we keep a dedicated connector
instead of reusing the Postgres one. IAM auth is supported via
``extra_params['auth_mode'] = 'iam'`` + ``iam_cluster_id`` / ``iam_db_user``.
"""

from __future__ import annotations

import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog

from app.infrastructure.connectors.base import BaseConnector
from app.infrastructure.connectors._ssl import local_schemas

logger = structlog.get_logger()

CONNECTION_TIMEOUT = 5
INTROSPECTION_TIMEOUT = 30.0

# Postgres SQLSTATEs that surface during a Redshift cluster cold-start or
# WLM queue recovery — both are transient and worth a second attempt.
_TRANSIENT_SQLSTATES = ("08001", "08006", "08000", "08003", "08004")
_TRANSIENT_MARKERS = (
    "connection",
    "cluster is restarting",
    "cluster is resuming",
)

_REDSHIFT_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="redshift")


def _sanitize_error(msg: str) -> str:
    return re.sub(r"(password|passwd|pwd|token)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)


def _is_transient(exc: Exception) -> bool:
    """True if the exception looks like a transient connect-time failure."""
    state = getattr(exc, "sqlstate", None) or getattr(exc, "code", None)
    if isinstance(state, str) and state in _TRANSIENT_SQLSTATES:
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


class RedshiftConnector(BaseConnector):
    """Amazon Redshift connector."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_mode = self._extra_params.get("auth_mode", "password")
        self._iam_cluster_id = self._extra_params.get("iam_cluster_id", "")
        self._iam_db_user = self._extra_params.get("iam_db_user", "")
        self._aws_region = self._extra_params.get("aws_region", "us-east-1")
        self._conn = None

    def _connect_sync(self):
        import redshift_connector

        # application_name flows into STL_QUERY for WLM bucketing + auditing.
        app_name = self._extra_params.get("application_name") or "datawrangler"

        attempts = int(self._extra_params.get("connect_retry_attempts") or 2)
        backoff = float(self._extra_params.get("connect_retry_backoff_sec") or 5.0)

        def _do_connect():
            if self._auth_mode == "iam":
                return redshift_connector.connect(
                    iam=True,
                    cluster_identifier=self._iam_cluster_id,
                    db_user=self._iam_db_user,
                    database=self._database_name,
                    region=self._aws_region,
                    ssl=True,
                    sslmode="verify-ca",
                    timeout=CONNECTION_TIMEOUT,
                    application_name=app_name,
                )
            return redshift_connector.connect(
                host=self._host,
                port=self._port,
                database=self._database_name,
                user=self._username,
                password=self._password,
                ssl=bool(self._extra_params.get("ssl", True)),
                sslmode="verify-ca" if not self._extra_params.get("ssl_trust_server_cert") else "require",
                timeout=CONNECTION_TIMEOUT,
                application_name=app_name,
            )

        last_exc: Exception | None = None
        for attempt in range(max(1, attempts)):
            try:
                return _do_connect()
            except Exception as exc:
                last_exc = exc
                if attempt + 1 >= attempts or not _is_transient(exc):
                    raise
                logger.warning(
                    "redshift_connect_retry",
                    attempt=attempt + 1,
                    of=attempts,
                    error=_sanitize_error(str(exc)),
                )
                time.sleep(backoff)
        # Defensive — the loop above either returns or raises.
        raise last_exc if last_exc else RuntimeError("redshift_connect_failed")

    def _get_conn_sync(self):
        if self._conn is None:
            self._conn = self._connect_sync()
        return self._conn

    async def _run(self, func, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_REDSHIFT_EXECUTOR, func, *args)

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
                logger.warning("connector_test_failed", connector="redshift", error=_sanitize_error(str(e)))
                return False

        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT + 5):
                return await self._run(_test)
        except Exception:
            return False

    async def get_schemas(self) -> list[dict[str, Any]]:
        allow = local_schemas(self._extra_params)

        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            cur = conn.cursor()
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_internal') "
                "ORDER BY schema_name"
            )
            schemas = [{"name": r[0]} for r in cur.fetchall()]
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
            cur.execute(
                "SELECT table_name, "
                "  (SELECT tbl_rows FROM svv_table_info "
                "    WHERE \"schema\" = t.table_schema AND \"table\" = t.table_name LIMIT 1) AS row_count, "
                "  (SELECT size * 1024 * 1024 FROM svv_table_info "
                "    WHERE \"schema\" = t.table_schema AND \"table\" = t.table_name LIMIT 1) AS size_bytes "
                "FROM information_schema.tables t "
                "WHERE t.table_schema = %s AND t.table_type = 'BASE TABLE' "
                "ORDER BY table_name",
                (schema,),
            )
            # svv_table_info is eventually consistent — counts can lag the
            # latest COPY by minutes. Surface that with row_count_stale=True
            # so the UI can render a "~" prefix and ops know not to trust
            # the figure for capacity calculations.
            tables = [
                {
                    "name": r[0],
                    "row_count": int(r[1] or 0),
                    "size_bytes": int(r[2] or 0),
                    "row_count_stale": True,
                }
                for r in cur.fetchall()
            ]
            cur.close()
            return tables

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run(_get)

    async def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            self._validate_table_sync(conn, schema, table)
            cur = conn.cursor()
            cur.execute(
                "SELECT column_name, data_type, is_nullable, "
                "character_maximum_length, numeric_precision "
                "FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s "
                "ORDER BY ordinal_position",
                (schema, table),
            )
            cols = cur.fetchall()

            cur.execute(
                "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "WHERE tc.constraint_type = 'PRIMARY KEY' "
                "  AND tc.table_schema = %s AND tc.table_name = %s",
                (schema, table),
            )
            pk_cols = {r[0] for r in cur.fetchall()}
            cur.close()

            return [
                {
                    "name": r[0],
                    "data_type": r[1],
                    "is_nullable": r[2] == "YES",
                    "character_maximum_length": r[3],
                    "numeric_precision": r[4],
                    "is_primary_key": r[0] in pk_cols,
                    "is_foreign_key": False,  # Redshift FKs are informational
                    "fk_references": None,
                }
                for r in cols
            ]

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run(_get)

    async def get_sample_data(self, schema: str, table: str, limit: int = 100) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            vs, vt = self._validate_table_sync(conn, schema, table)
            cur = conn.cursor()
            cur.execute(f'SELECT * FROM "{vs}"."{vt}" LIMIT %s', (min(limit, 1000),))
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
        cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s", (schema,))
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Schema '{schema}' does not exist")
        return row[0]

    def _validate_table_sync(self, conn, schema: str, table: str) -> tuple[str, str]:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = %s",
            (schema, table),
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Table '{schema}.{table}' does not exist")
        return row[0], row[1]
