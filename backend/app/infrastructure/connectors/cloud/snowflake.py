"""Snowflake connector using snowflake-connector-python (sync, wrapped in executor)."""

from __future__ import annotations

import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
import structlog

from app.infrastructure.connectors.base import BaseConnector
from app.infrastructure.connectors._ssl import local_schemas

logger = structlog.get_logger()

CONNECTION_TIMEOUT = 5
INTROSPECTION_TIMEOUT = 30.0

# Dedicated thread pool — prevents Snowflake sync calls from exhausting the default executor
_SNOWFLAKE_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="snowflake")


def _sanitize_error(msg: str) -> str:
    return re.sub(r"(password|passwd|pwd|token)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)


def _load_private_key(pem: str, passphrase: str | None) -> bytes:
    """Decode a PEM private key into the DER-encoded PKCS#8 bytes Snowflake wants."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(
        pem.encode() if isinstance(pem, str) else pem,
        password=passphrase.encode() if passphrase else None,
        backend=default_backend(),
    )
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class SnowflakeConnector(BaseConnector):
    """Snowflake connector — sync driver wrapped in dedicated thread pool."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._account = self._extra_params.get("account", "")
        self._warehouse = self._extra_params.get("warehouse", "")
        self._role = self._extra_params.get("role", "")
        self._auth_mode = self._extra_params.get("auth_mode", "password")
        self._private_key_pem = self._extra_params.get("private_key_pem", "")
        self._private_key_passphrase = self._extra_params.get("private_key_passphrase", "")
        # Pre-acquired OAuth access token. If ``oauth_refresh_token`` is also
        # supplied we treat ``oauth_token`` as a cache that we'll refresh
        # automatically when it expires.
        self._oauth_token = self._extra_params.get("oauth_token", "")
        self._oauth_refresh_token = self._extra_params.get("oauth_refresh_token", "")
        self._oauth_client_id = self._extra_params.get("oauth_client_id", "")
        self._oauth_client_secret = self._extra_params.get("oauth_client_secret", "")
        self._oauth_token_endpoint = self._extra_params.get("oauth_token_endpoint", "")
        self._oauth_token_expires_at: float = 0.0
        # SAML/Okta authenticator URL — e.g. ``https://my-okta-org.okta.com``.
        self._okta_url = self._extra_params.get("okta_url", "")
        self._conn = None

    def _build_session_parameters(self) -> dict[str, Any]:
        """Session-level parameters for billing attribution + hard timeouts.

        ``QUERY_TAG`` flows into Snowflake's QUERY_HISTORY for chargeback;
        ``STATEMENT_TIMEOUT_IN_SECONDS`` prevents a runaway introspection
        from holding a warehouse warm indefinitely.
        """
        tag = self._extra_params.get("query_tag") or "datawrangler"
        timeout = int(self._extra_params.get("statement_timeout_seconds") or 300)
        params: dict[str, Any] = {
            "QUERY_TAG": tag,
            "STATEMENT_TIMEOUT_IN_SECONDS": timeout,
        }
        extra = self._extra_params.get("session_parameters")
        if isinstance(extra, dict):
            params.update(extra)
        return params

    def _connect_sync(self):
        import snowflake.connector

        common: dict[str, Any] = {
            "account": self._account,
            "user": self._username,
            "database": self._database_name,
            "warehouse": self._warehouse,
            "role": self._role or None,
            "login_timeout": CONNECTION_TIMEOUT,
            "network_timeout": INTROSPECTION_TIMEOUT,
            "session_parameters": self._build_session_parameters(),
        }
        if self._auth_mode == "key_pair":
            common["private_key"] = _load_private_key(
                self._private_key_pem, self._private_key_passphrase or None
            )
        elif self._auth_mode == "oauth":
            common["authenticator"] = "oauth"
            common["token"] = self._ensure_oauth_token()
        elif self._auth_mode == "okta":
            # Native SAML — Snowflake's authenticator is the Okta org URL.
            # The username is the Okta principal; password is the Okta one.
            if not self._okta_url:
                raise ValueError(
                    "Snowflake Okta auth requires ``okta_url`` (e.g. "
                    "https://my-org.okta.com). Get it from your IdP admin."
                )
            common["authenticator"] = self._okta_url
            common["password"] = self._password
        elif self._auth_mode == "externalbrowser":
            # Explicitly opt-in for interactive desktop sessions only.
            common["authenticator"] = "externalbrowser"
        else:
            common["password"] = self._password
        return snowflake.connector.connect(**common)

    def _ensure_oauth_token(self) -> str:
        """Return a valid access token, refreshing if a refresh token exists.

        Static tokens (no refresh flow configured) are returned as-is and
        the user is expected to rotate them out-of-band; we fall back to
        the static path because some IdPs hand out long-lived service tokens.
        """
        # Fast path: static token, no refresh capability.
        if not (self._oauth_refresh_token and self._oauth_client_id and self._oauth_token_endpoint):
            if not self._oauth_token:
                raise ValueError(
                    "Snowflake OAuth requires either a static ``oauth_token`` or "
                    "the full refresh-token quad (oauth_refresh_token, "
                    "oauth_client_id, oauth_client_secret, oauth_token_endpoint)."
                )
            return self._oauth_token

        # Refresh path: re-mint when within 60s of expiry.
        if self._oauth_token and time.time() < self._oauth_token_expires_at - 60:
            return self._oauth_token

        with httpx.Client(timeout=10) as client:
            resp = client.post(
                self._oauth_token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._oauth_refresh_token,
                    "client_id": self._oauth_client_id,
                    "client_secret": self._oauth_client_secret,
                },
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Snowflake OAuth refresh failed ({resp.status_code}): "
                f"{_sanitize_error(resp.text)[:200]}"
            )
        body = resp.json()
        self._oauth_token = body["access_token"]
        self._oauth_token_expires_at = time.time() + int(body.get("expires_in", 3600))
        return self._oauth_token

    def _get_conn_sync(self):
        if self._conn is None or self._conn.is_closed():
            self._conn = self._connect_sync()
        return self._conn

    async def _run_sync(self, func, *args):
        """Run sync Snowflake operation in dedicated thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_SNOWFLAKE_EXECUTOR, func, *args)

    async def test_connection(self) -> bool:
        def _test():
            try:
                conn = self._connect_sync()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.close()
                return True
            except Exception as e:
                logger.warning("connector_test_failed", connector="snowflake", error=_sanitize_error(str(e)))
                return False

        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT + 5):
                return await self._run_sync(_test)
        except Exception:
            return False

    async def get_schemas(self) -> list[dict[str, Any]]:
        allow = local_schemas(self._extra_params)

        def _get():
            conn = self._get_conn_sync()
            cur = conn.cursor()
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE catalog_name = %s AND schema_name NOT IN ('INFORMATION_SCHEMA') "
                "ORDER BY schema_name",
                (self._database_name,),
            )
            rows = cur.fetchall()
            cur.close()
            schemas = [{"name": row[0]} for row in rows]
            if allow is not None:
                allowed = {s.upper() for s in allow}
                schemas = [s for s in schemas if s["name"].upper() in allowed]
            return schemas

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run_sync(_get)

    async def get_tables(self, schema: str) -> list[dict[str, Any]]:
        def _get():
            conn = self._get_conn_sync()
            self._validate_schema_sync(conn, schema)
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name, row_count, bytes "
                "FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
                "ORDER BY table_name",
                (schema,),
            )
            rows = cur.fetchall()
            cur.close()
            return [{"name": r[0], "row_count": r[1] or 0, "size_bytes": r[2] or 0} for r in rows]

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run_sync(_get)

    async def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        # Snowflake stores FK metadata in INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
        # but does NOT enforce them at write time. We still surface them so the
        # Database View can render FK badges and subsetting can derive a
        # dependency graph. ``enable_fk`` extra param defaults to true.
        enable_fk = bool(self._extra_params.get("enable_fk", True))

        def _get():
            conn = self._get_conn_sync()
            self._validate_table_sync(conn, schema, table)
            cur = conn.cursor()
            cur.execute(
                "SELECT column_name, data_type, is_nullable, character_maximum_length, numeric_precision "
                "FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s "
                "ORDER BY ordinal_position",
                (schema, table),
            )
            rows = cur.fetchall()

            # PK info
            cur.execute(
                "SELECT column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
                "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s AND tc.table_name = %s",
                (schema, table),
            )
            pk_cols = {r[0] for r in cur.fetchall()}

            fk_by_col: dict[str, dict[str, str]] = {}
            if enable_fk:
                try:
                    cur.execute(
                        "SELECT kcu.column_name, "
                        "       rc.unique_constraint_schema, "
                        "       rc.unique_constraint_name "
                        "FROM information_schema.referential_constraints rc "
                        "JOIN information_schema.key_column_usage kcu "
                        "  ON kcu.constraint_name = rc.constraint_name "
                        " AND kcu.constraint_schema = rc.constraint_schema "
                        "WHERE kcu.table_schema = %s AND kcu.table_name = %s",
                        (schema, table),
                    )
                    for col_name, ref_schema, ref_name in cur.fetchall():
                        fk_by_col[col_name] = {
                            "schema": ref_schema,
                            "constraint": ref_name,
                        }
                except Exception as e:
                    # Older Snowflake editions or restricted roles may reject
                    # the join — degrade quietly rather than breaking discovery.
                    logger.debug("snowflake_fk_lookup_failed", error=_sanitize_error(str(e)))
            cur.close()

            return [
                {
                    "name": r[0],
                    "data_type": r[1],
                    "is_nullable": r[2] == "YES",
                    "character_maximum_length": r[3],
                    "numeric_precision": r[4],
                    "is_primary_key": r[0] in pk_cols,
                    "is_foreign_key": r[0] in fk_by_col,
                    "fk_references": fk_by_col.get(r[0]),
                }
                for r in rows
            ]

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run_sync(_get)

    async def get_sample_data(self, schema: str, table: str, limit: int = 100) -> list[dict[str, Any]]:
        def _get():
            conn = self._get_conn_sync()
            vs, vt = self._validate_table_sync(conn, schema, table)
            cur = conn.cursor()
            # Use 3-part naming so multi-database accounts don't resolve the
            # sample query against whichever DB was last touched on this
            # session. ``_database_name`` is required on this connector — its
            # absence has always been a misconfiguration, not optional state.
            db = self._database_name
            cur.execute(f'SELECT * FROM "{db}"."{vs}"."{vt}" LIMIT %s', (min(limit, 1000),))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            cur.close()
            return [dict(zip(columns, row)) for row in rows]

        async with asyncio.timeout(INTROSPECTION_TIMEOUT):
            return await self._run_sync(_get)

    async def close(self) -> None:
        def _close():
            if self._conn and not self._conn.is_closed():
                self._conn.close()
                self._conn = None
        await self._run_sync(_close)

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
            "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
            (schema, table),
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Table '{schema}.{table}' does not exist")
        return row[0], row[1]
