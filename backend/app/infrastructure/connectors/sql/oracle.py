"""Oracle connector using python-oracledb (thin mode, no Oracle client needed)."""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog

from app.infrastructure.connectors.base import BaseConnector
from app.infrastructure.connectors._ssl import build_driver_ssl_kwargs, local_schemas

logger = structlog.get_logger()

CONNECTION_TIMEOUT = 5
INTROSPECTION_TIMEOUT = 30.0

_ORACLE_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="oracle")


def _sanitize_error(msg: str) -> str:
    return re.sub(r"(password|passwd|pwd)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)


class OracleConnector(BaseConnector):
    """Oracle connector — oracledb thin-mode wrapped in dedicated thread pool.

    Service name comes from ``extra_params['service_name']``; if absent we fall
    back to using ``database_name`` as a SID for legacy installs.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._service_name = self._extra_params.get("service_name", "")
        self._pdb = self._extra_params.get("oracle_pdb") or ""
        # Auth modes: "password" (default), "kerberos" (externalauth via OS
        # ticket cache), "azure_ad" (access_token callable from extras).
        self._auth_mode = self._extra_params.get("auth_mode", "password")
        self._azure_ad_token = self._extra_params.get("azure_ad_token", "")
        self._conn = None

    def _connect_sync(self):
        import oracledb

        dsn_kwargs = {"host": self._host, "port": self._port}
        if self._service_name:
            dsn_kwargs["service_name"] = self._service_name
        else:
            dsn_kwargs["sid"] = self._database_name

        connect_kwargs: dict[str, Any] = {
            "dsn": oracledb.makedsn(**dsn_kwargs),
            "tcp_connect_timeout": CONNECTION_TIMEOUT,
        }
        connect_kwargs.update(build_driver_ssl_kwargs(self._extra_params, "oracle"))

        if self._auth_mode == "kerberos":
            # ``externalauth=True`` tells oracledb to use the OS-level
            # Kerberos ticket (KRB5CCNAME); user/password are ignored by
            # the driver in this mode.
            connect_kwargs["externalauth"] = True
        elif self._auth_mode == "azure_ad":
            if not self._azure_ad_token:
                raise ValueError(
                    "Oracle Azure AD auth requires ``azure_ad_token`` (a JWT "
                    "acquired from Azure AD with the Oracle Database scope)."
                )
            # oracledb 2.4+ accepts a callable that returns a fresh token —
            # ours returns the static token we were handed; rotate at the
            # connection-edit layer when the token is close to expiry.
            connect_kwargs["access_token"] = lambda *_: self._azure_ad_token
            connect_kwargs["user"] = self._username  # principal still required
        else:
            connect_kwargs["user"] = self._username
            connect_kwargs["password"] = self._password

        conn = oracledb.connect(**connect_kwargs)
        if self._pdb:
            if not self._pdb.replace("_", "").isalnum():
                raise ValueError(f"Invalid Oracle PDB name '{self._pdb}'")
            cur = conn.cursor()
            try:
                cur.execute(f'ALTER SESSION SET CONTAINER = "{self._pdb}"')
            finally:
                cur.close()
        return conn

    def _get_conn_sync(self):
        if self._conn is None:
            self._conn = self._connect_sync()
        return self._conn

    async def _run(self, func, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_ORACLE_EXECUTOR, func, *args)

    async def test_connection(self) -> bool:
        def _test() -> bool:
            try:
                conn = self._connect_sync()
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM DUAL")
                cur.close()
                conn.close()
                return True
            except Exception as e:
                logger.warning("connector_test_failed", connector="oracle", error=_sanitize_error(str(e)))
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
                "SELECT username FROM all_users "
                "WHERE oracle_maintained = 'N' ORDER BY username"
            )
            schemas = [{"name": row[0]} for row in cur.fetchall()]
            cur.close()
            if allow is not None:
                allowed = {s.upper() for s in allow}
                schemas = [s for s in schemas if s["name"].upper() in allowed]
            return schemas

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run(_get)

    async def get_tables(self, schema: str) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            self._validate_schema_sync(conn, schema)
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name, num_rows, blocks * 8192 AS size_bytes "
                "FROM all_tables WHERE owner = :owner ORDER BY table_name",
                owner=schema.upper(),
            )
            tables = [
                {"name": r[0], "row_count": r[1] or 0, "size_bytes": r[2] or 0}
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
                "SELECT column_name, data_type, nullable, data_length, data_precision "
                "FROM all_tab_columns WHERE owner = :owner AND table_name = :tname "
                "ORDER BY column_id",
                owner=schema.upper(),
                tname=table.upper(),
            )
            cols = cur.fetchall()

            cur.execute(
                "SELECT acc.column_name "
                "FROM all_constraints ac "
                "JOIN all_cons_columns acc ON ac.constraint_name = acc.constraint_name "
                "WHERE ac.constraint_type = 'P' AND ac.owner = :owner AND ac.table_name = :tname",
                owner=schema.upper(),
                tname=table.upper(),
            )
            pk_cols = {r[0] for r in cur.fetchall()}

            cur.execute(
                "SELECT acc.column_name, r_owner.owner AS ref_owner, r_owner.table_name AS ref_table, r_owner.column_name AS ref_column "
                "FROM all_constraints ac "
                "JOIN all_cons_columns acc ON ac.constraint_name = acc.constraint_name "
                "JOIN all_cons_columns r_owner ON ac.r_constraint_name = r_owner.constraint_name "
                "WHERE ac.constraint_type = 'R' AND ac.owner = :owner AND ac.table_name = :tname",
                owner=schema.upper(),
                tname=table.upper(),
            )
            fk_map = {r[0]: {"schema": r[1], "table": r[2], "column": r[3]} for r in cur.fetchall()}
            cur.close()

            return [
                {
                    "name": r[0],
                    "data_type": r[1].lower(),
                    "is_nullable": r[2] == "Y",
                    "character_maximum_length": r[3],
                    "numeric_precision": r[4],
                    "is_primary_key": r[0] in pk_cols,
                    "is_foreign_key": r[0] in fk_map,
                    "fk_references": fk_map.get(r[0]),
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
            cur.execute(
                f'SELECT * FROM "{vs}"."{vt}" FETCH FIRST :n ROWS ONLY',
                n=min(limit, 1000),
            )
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
        cur.execute("SELECT username FROM all_users WHERE username = :u", u=schema.upper())
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Schema '{schema}' does not exist")
        return row[0]

    def _validate_table_sync(self, conn, schema: str, table: str) -> tuple[str, str]:
        cur = conn.cursor()
        cur.execute(
            "SELECT owner, table_name FROM all_tables WHERE owner = :o AND table_name = :t",
            o=schema.upper(),
            t=table.upper(),
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Table '{schema}.{table}' does not exist")
        return row[0], row[1]
