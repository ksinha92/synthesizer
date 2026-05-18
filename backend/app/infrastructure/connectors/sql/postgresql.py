"""PostgreSQL connector using asyncpg with a per-connector connection pool."""

from __future__ import annotations

import asyncio
import os
import ssl as ssl_module
from typing import Any

import asyncpg
import structlog

from app.infrastructure.connectors.base import BaseConnector
from app.infrastructure.connectors._ssl import build_ssl_context, kerberos_enabled, local_schemas

logger = structlog.get_logger()

CONNECTION_TIMEOUT = 5.0  # seconds for test_connection
INTROSPECTION_TIMEOUT = 30.0  # seconds for schema queries
COMMAND_TIMEOUT = 60.0  # per-query hard cap

POOL_MIN_SIZE = 1  # introspection workloads are spiky, don't pre-warm
POOL_MAX_SIZE = 10
POOL_IDLE_LIFETIME = 300.0  # close sockets idle > 5 min


class PostgreSQLConnector(BaseConnector):
    """PostgreSQL connector using an asyncpg connection pool.

    The pool is created lazily on first introspection call. ``test_connection``
    keeps its one-shot semantics so a misconfigured connection fails fast
    without leaving a pool behind.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pool: asyncpg.Pool | None = None

    def _build_connect_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "host": self._host,
            "port": self._port,
            "database": self._database_name,
            "user": self._username,
            "password": self._password,
            "timeout": CONNECTION_TIMEOUT,
        }
        ctx = build_ssl_context(self._extra_params)
        if ctx is not None:
            kwargs["ssl"] = ctx
        elif self._extra_params.get("ssl"):
            kwargs["ssl"] = ssl_module.create_default_context()
        if kerberos_enabled(self._extra_params):
            self._configure_kerberos(kwargs)
        return kwargs

    def _configure_kerberos(self, kwargs: dict[str, Any]) -> None:
        """Wire Kerberos/GSSAPI auth into asyncpg.

        asyncpg uses libpq's GSSAPI support under the hood, which means the
        container/worker process MUST have:
            - libgssapi-krb5-2 installed
            - a valid TGT in ``KRB5CCNAME`` (or default /tmp/krb5cc_uid)
            - ``krb5.conf`` pointing at the realm's KDC

        Without those, libpq will silently fall back to password auth and
        the user gets a confusing "authentication failed" error. We refuse
        to start if the ticket cache env var is missing — much clearer
        than a buried libpq error 20 levels deep.
        """
        # MIT Kerberos's default cache path is ``/tmp/krb5cc_<uid>`` — only
        # uid=0 lands at ``/tmp/krb5cc_0``. Most production workers run as
        # non-root, so probing only the root path falsely rejects perfectly
        # valid default caches. Use ``os.getuid()`` (POSIX-only — Windows
        # callers always have ``KRB5CCNAME`` from MIT Kerberos for Windows).
        default_cache = (
            f"/tmp/krb5cc_{os.getuid()}" if hasattr(os, "getuid") else None
        )
        if (
            not os.environ.get("KRB5CCNAME")
            and (default_cache is None or not os.path.exists(default_cache))
        ):
            raise RuntimeError(
                "PostgreSQL Kerberos auth requires a valid Kerberos ticket. "
                f"No ticket cache found at default path ({default_cache or 'platform-specific'}). "
                "Set KRB5CCNAME to a ticket cache (run ``kinit`` first), "
                "or disable kerberosEnabled in the connection settings."
            )
        principal = self._extra_params.get("kerberos_principal") or self._username
        if principal:
            # ``user`` becomes the Kerberos principal; password is ignored.
            kwargs["user"] = principal
            kwargs["password"] = ""
        # ``krbsrvname`` is the service principal name the server is
        # registered under in the KDC. Default ``postgres`` matches almost
        # every prod cluster; override via extras if your DBA chose differently.
        kwargs["server_settings"] = {
            **(kwargs.get("server_settings") or {}),
            "krbsrvname": self._extra_params.get("krb_service_name") or "postgres",
            "application_name": f"datawrangler/{principal}" if principal else "datawrangler",
        }

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                max_inactive_connection_lifetime=POOL_IDLE_LIFETIME,
                command_timeout=COMMAND_TIMEOUT,
                **self._build_connect_kwargs(),
            )
        return self._pool

    async def test_connection(self) -> bool:
        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT):
                conn = await asyncpg.connect(**self._build_connect_kwargs())
                await conn.fetchval("SELECT 1")
                await conn.close()
                return True
        except Exception as e:
            await logger.awarning("connector_test_failed", connector="postgresql", error=str(e))
            return False

    async def get_schemas(self) -> list[dict[str, Any]]:
        allow = local_schemas(self._extra_params)
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                    ORDER BY schema_name
                    """
                )
            schemas = [{"name": row["schema_name"]} for row in rows]
            if allow is not None:
                allowed = {s.lower() for s in allow}
                schemas = [s for s in schemas if s["name"].lower() in allowed]
            return schemas

    async def get_tables(self, schema: str) -> list[dict[str, Any]]:
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await self._validate_schema(conn, schema)
                rows = await conn.fetch(
                    """
                    SELECT
                        t.table_name,
                        COALESCE(s.n_live_tup, 0) AS row_count,
                        COALESCE(pg_total_relation_size(quote_ident($1) || '.' || quote_ident(t.table_name)), 0) AS size_bytes
                    FROM information_schema.tables t
                    LEFT JOIN pg_stat_user_tables s
                        ON s.schemaname = t.table_schema AND s.relname = t.table_name
                    WHERE t.table_schema = $1
                        AND t.table_type = 'BASE TABLE'
                    ORDER BY t.table_name
                    """,
                    schema,
                )
            return [
                {
                    "name": row["table_name"],
                    "row_count": row["row_count"],
                    "size_bytes": row["size_bytes"],
                }
                for row in rows
            ]

    async def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await self._validate_table(conn, schema, table)
                rows = await conn.fetch(
                    """
                    SELECT
                        c.column_name,
                        c.data_type,
                        c.is_nullable = 'YES' AS is_nullable,
                        c.character_maximum_length,
                        c.numeric_precision,
                        EXISTS (
                            SELECT 1 FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_name = kcu.constraint_name
                                AND tc.table_schema = kcu.table_schema
                            WHERE tc.constraint_type = 'PRIMARY KEY'
                                AND tc.table_schema = $1
                                AND tc.table_name = $2
                                AND kcu.column_name = c.column_name
                        ) AS is_primary_key,
                        EXISTS (
                            SELECT 1 FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_name = kcu.constraint_name
                                AND tc.table_schema = kcu.table_schema
                            WHERE tc.constraint_type = 'FOREIGN KEY'
                                AND tc.table_schema = $1
                                AND tc.table_name = $2
                                AND kcu.column_name = c.column_name
                        ) AS is_foreign_key
                    FROM information_schema.columns c
                    WHERE c.table_schema = $1 AND c.table_name = $2
                    ORDER BY c.ordinal_position
                    """,
                    schema,
                    table,
                )

                fk_rows = await conn.fetch(
                    """
                    SELECT
                        kcu.column_name,
                        ccu.table_schema AS ref_schema,
                        ccu.table_name AS ref_table,
                        ccu.column_name AS ref_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu
                        ON tc.constraint_name = ccu.constraint_name
                        AND tc.table_schema = ccu.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = $1
                        AND tc.table_name = $2
                    """,
                    schema,
                    table,
                )

            fk_map = {
                row["column_name"]: {
                    "schema": row["ref_schema"],
                    "table": row["ref_table"],
                    "column": row["ref_column"],
                }
                for row in fk_rows
            }

            return [
                {
                    "name": row["column_name"],
                    "data_type": row["data_type"],
                    "is_nullable": row["is_nullable"],
                    "character_maximum_length": row["character_maximum_length"],
                    "numeric_precision": row["numeric_precision"],
                    "is_primary_key": row["is_primary_key"],
                    "is_foreign_key": row["is_foreign_key"],
                    "fk_references": fk_map.get(row["column_name"]),
                }
                for row in rows
            ]

    async def get_sample_data(self, schema: str, table: str, limit: int = 100) -> list[dict[str, Any]]:
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                validated_schema, validated_table = await self._validate_table(conn, schema, table)
                rows = await conn.fetch(
                    f'SELECT * FROM "{validated_schema}"."{validated_table}" LIMIT $1',
                    min(limit, 1000),
                )
            return [dict(row) for row in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _validate_schema(self, conn: asyncpg.Connection, schema: str) -> str:
        result = await conn.fetchval(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = $1",
            schema,
        )
        if result is None:
            raise ValueError(f"Schema '{schema}' does not exist")
        return result

    async def _validate_table(self, conn: asyncpg.Connection, schema: str, table: str) -> tuple[str, str]:
        row = await conn.fetchrow(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema = $1 AND table_name = $2
            """,
            schema,
            table,
        )
        if row is None:
            raise ValueError(f"Table '{schema}.{table}' does not exist")
        return row["table_schema"], row["table_name"]
