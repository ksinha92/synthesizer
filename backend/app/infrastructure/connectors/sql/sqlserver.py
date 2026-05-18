"""SQL Server connector using pyodbc + Microsoft ODBC Driver 18.

pyodbc is the only Python driver that supports the full SQL Server auth
matrix that enterprises need (SQL auth, Azure AD access token, Azure AD
password, Windows Integrated/Kerberos). It also supports ``TrustServerCertificate``
and ``Encrypt`` settings natively via the ODBC connection string.

The Microsoft ODBC Driver for SQL Server (``msodbcsql18``) must be installed
on the worker host — without it, ``pyodbc.connect`` raises a
``pyodbc.InterfaceError`` that we surface up unchanged.
"""

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
INTROSPECTION_TIMEOUT = 30.0

_SQLSERVER_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sqlserver")


def _sanitize_error(msg: str) -> str:
    return re.sub(r"(password|passwd|pwd)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)


class SQLServerConnector(BaseConnector):
    """SQL Server connector using pyodbc.

    Auth modes:
        - ``password`` (default) — SQL Server auth via UID/PWD
        - ``azure_ad`` — Azure AD access token (SQL_COPT_SS_ACCESS_TOKEN=1256)
        - ``windows`` — Windows Integrated / Kerberos via OS session
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._instance = self._extra_params.get("instance", "")
        self._auth_mode = (self._extra_params.get("auth_mode") or "password").lower()
        self._azure_ad_token = self._extra_params.get("azure_ad_token", "")
        self._encrypt = bool(self._extra_params.get("ssl"))
        self._trust_server_cert = bool(self._extra_params.get("ssl_trust_server_cert"))
        self._driver = self._extra_params.get("pyodbc_driver") or "ODBC Driver 18 for SQL Server"
        self._conn = None

    def _build_conn_str(self) -> str:
        server = f"{self._host}\\{self._instance}" if self._instance else self._host
        parts = [
            f"DRIVER={{{self._driver}}}",
            f"SERVER={server},{self._port}",
            f"DATABASE={self._database_name}",
            "Encrypt=yes" if self._encrypt else "Encrypt=no",
            f"TrustServerCertificate={'yes' if self._trust_server_cert else 'no'}",
            f"Connection Timeout={CONNECTION_TIMEOUT}",
        ]
        if self._auth_mode == "windows":
            parts.append("Trusted_Connection=yes")
        elif self._auth_mode == "password":
            parts.append(f"UID={self._username}")
            parts.append(f"PWD={self._password}")
        # Azure AD: credentials supplied via attrs_before, not the string.
        return ";".join(parts) + ";"

    def _build_attrs(self) -> dict[int, Any] | None:
        if self._auth_mode != "azure_ad":
            return None
        if not self._azure_ad_token:
            raise ValueError(
                "Azure AD auth requires ``azure_ad_token`` (an access token "
                "with the SQL Database scope, acquired from Azure AD)."
            )
        # SQL_COPT_SS_ACCESS_TOKEN = 1256; token is a UCS-2 byte stream
        # prefixed by its 4-byte length. Microsoft's published pattern.
        token_bytes = self._azure_ad_token.encode("utf-16-le")
        token_struct = len(token_bytes).to_bytes(4, byteorder="little") + token_bytes
        return {1256: token_struct}

    def _connect_sync(self):
        try:
            import pyodbc
        except ImportError as exc:
            raise ImportError(
                "SQL Server requires the `pyodbc` package and the Microsoft "
                "ODBC Driver for SQL Server (msodbcsql18). Install both in "
                "the worker image."
            ) from exc

        conn_str = self._build_conn_str()
        attrs = self._build_attrs()
        if attrs is not None:
            return pyodbc.connect(conn_str, attrs_before=attrs)
        return pyodbc.connect(conn_str)

    def _get_conn_sync(self):
        if self._conn is None:
            self._conn = self._connect_sync()
        return self._conn

    async def _run(self, func, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_SQLSERVER_EXECUTOR, func, *args)

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
                logger.warning("connector_test_failed", connector="sqlserver", error=_sanitize_error(str(e)))
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
                "WHERE schema_name NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
                "'db_accessadmin','db_backupoperator','db_datareader','db_datawriter',"
                "'db_ddladmin','db_denydatareader','db_denydatawriter','db_securityadmin') "
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
            # pyodbc uses ``?`` placeholders.
            cur.execute(
                "SELECT t.name AS table_name, p.rows AS row_count, "
                "SUM(a.total_pages) * 8 * 1024 AS size_bytes "
                "FROM sys.tables t "
                "INNER JOIN sys.schemas s ON s.schema_id = t.schema_id "
                "INNER JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1) "
                "INNER JOIN sys.allocation_units a ON a.container_id = p.partition_id "
                "WHERE s.name = ? "
                "GROUP BY t.name, p.rows "
                "ORDER BY t.name",
                (schema,),
            )
            tables = [{"name": r[0], "row_count": int(r[1] or 0), "size_bytes": int(r[2] or 0)} for r in cur.fetchall()]
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
                "WHERE table_schema = ? AND table_name = ? "
                "ORDER BY ordinal_position",
                (schema, table),
            )
            cols = cur.fetchall()

            cur.execute(
                "SELECT kcu.column_name "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name = kcu.constraint_name "
                "WHERE tc.constraint_type = 'PRIMARY KEY' "
                "  AND tc.table_schema = ? AND tc.table_name = ?",
                (schema, table),
            )
            pk_cols = {r[0] for r in cur.fetchall()}

            cur.execute(
                "SELECT kcu1.column_name, kcu2.table_schema, kcu2.table_name, kcu2.column_name "
                "FROM information_schema.referential_constraints rc "
                "JOIN information_schema.key_column_usage kcu1 "
                "  ON kcu1.constraint_name = rc.constraint_name "
                "JOIN information_schema.key_column_usage kcu2 "
                "  ON kcu2.constraint_name = rc.unique_constraint_name "
                "WHERE kcu1.table_schema = ? AND kcu1.table_name = ?",
                (schema, table),
            )
            fk_map = {r[0]: {"schema": r[1], "table": r[2], "column": r[3]} for r in cur.fetchall()}
            cur.close()

            return [
                {
                    "name": r[0],
                    "data_type": r[1],
                    "is_nullable": r[2] == "YES",
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
            n = min(limit, 1000)
            # Validated identifiers; bracket-quoted to handle reserved words.
            cur.execute(f'SELECT TOP {n} * FROM [{vs}].[{vt}]')
            col_names = [d[0] for d in cur.description]
            rows = [dict(zip(col_names, r)) for r in cur.fetchall()]
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
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = ?",
            (schema,),
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Schema '{schema}' does not exist")
        return row[0]

    def _validate_table_sync(self, conn, schema: str, table: str) -> tuple[str, str]:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema = ? AND table_name = ?",
            (schema, table),
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Table '{schema}.{table}' does not exist")
        return row[0], row[1]
