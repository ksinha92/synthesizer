"""MySQL connector using aiomysql with a per-connector connection pool."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import aiomysql
import structlog

from app.infrastructure.connectors.base import BaseConnector
from app.infrastructure.connectors._ssl import build_ssl_context, local_schemas

logger = structlog.get_logger()

CONNECTION_TIMEOUT = 5.0
INTROSPECTION_TIMEOUT = 30.0

POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 10
POOL_RECYCLE_SECONDS = 3600  # recycle every hour to dodge firewall idle drops


def _sanitize_error(msg: str) -> str:
    return re.sub(r"(password|passwd|pwd)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)


class MySQLConnector(BaseConnector):
    """MySQL connector using an aiomysql pool."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pool: aiomysql.Pool | None = None

    def _build_connect_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "host": self._host,
            "port": self._port,
            "db": self._database_name,
            "user": self._username,
            "password": self._password,
            "connect_timeout": int(CONNECTION_TIMEOUT),
        }
        ctx = build_ssl_context(self._extra_params)
        if ctx is not None:
            kwargs["ssl"] = ctx
        if charset := self._extra_params.get("charset"):
            kwargs["charset"] = charset
        if plugin := self._extra_params.get("auth_plugin"):
            kwargs["auth_plugin"] = plugin
        return kwargs

    async def _get_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                minsize=POOL_MIN_SIZE,
                maxsize=POOL_MAX_SIZE,
                pool_recycle=POOL_RECYCLE_SECONDS,
                **self._build_connect_kwargs(),
            )
        return self._pool

    async def test_connection(self) -> bool:
        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT):
                conn = await aiomysql.connect(**self._build_connect_kwargs())
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                conn.close()
                return True
        except Exception as e:
            await logger.awarning("connector_test_failed", connector="mysql", error=_sanitize_error(str(e)))
            return False

    async def get_schemas(self) -> list[dict[str, Any]]:
        allow = local_schemas(self._extra_params)
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        "SELECT schema_name FROM information_schema.schemata "
                        "WHERE schema_name NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys') "
                        "ORDER BY schema_name"
                    )
                    rows = await cur.fetchall()
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
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        "SELECT table_name, table_rows AS row_count, "
                        "data_length + index_length AS size_bytes "
                        "FROM information_schema.tables "
                        "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
                        "ORDER BY table_name",
                        (schema,),
                    )
                    rows = await cur.fetchall()
            return [{"name": r["table_name"], "row_count": r["row_count"] or 0, "size_bytes": r["size_bytes"] or 0} for r in rows]

    async def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await self._validate_table(conn, schema, table)
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        "SELECT c.column_name, c.data_type, c.is_nullable = 'YES' AS is_nullable, "
                        "c.character_maximum_length, c.numeric_precision, c.column_key "
                        "FROM information_schema.columns c "
                        "WHERE c.table_schema = %s AND c.table_name = %s "
                        "ORDER BY c.ordinal_position",
                        (schema, table),
                    )
                    col_rows = await cur.fetchall()

                    await cur.execute(
                        "SELECT column_name, referenced_table_schema, referenced_table_name, referenced_column_name "
                        "FROM information_schema.key_column_usage "
                        "WHERE table_schema = %s AND table_name = %s AND referenced_table_name IS NOT NULL",
                        (schema, table),
                    )
                    fk_rows = await cur.fetchall()

            fk_map = {
                r["column_name"]: {"schema": r["referenced_table_schema"], "table": r["referenced_table_name"], "column": r["referenced_column_name"]}
                for r in fk_rows
            }

            return [
                {
                    "name": r["column_name"],
                    "data_type": r["data_type"],
                    "is_nullable": bool(r["is_nullable"]),
                    "character_maximum_length": r["character_maximum_length"],
                    "numeric_precision": r["numeric_precision"],
                    "is_primary_key": r["column_key"] == "PRI",
                    "is_foreign_key": r["column_name"] in fk_map,
                    "fk_references": fk_map.get(r["column_name"]),
                }
                for r in col_rows
            ]

    async def get_sample_data(self, schema: str, table: str, limit: int = 100) -> list[dict[str, Any]]:
        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                validated_schema, validated_table = await self._validate_table(conn, schema, table)
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        f"SELECT * FROM `{validated_schema}`.`{validated_table}` LIMIT %s",
                        (min(limit, 1000),),
                    )
                    rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def _validate_schema(self, conn, schema: str) -> str:
        async with conn.cursor() as cur:
            await cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s", (schema,))
            row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Schema '{schema}' does not exist")
        return row[0]

    async def _validate_table(self, conn, schema: str, table: str) -> tuple[str, str]:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
                (schema, table),
            )
            row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Table '{schema}.{table}' does not exist")
        return row[0], row[1]
