"""IBM DB2 connector using ibm_db_dbi (sync) wrapped in executor.

Critical for Ameritas — DB2 backs the legacy policy administration system that
underpins much of the insurance datawarehouse.

Supports both **DB2 LUW** (Linux/Unix/Windows — default) and **DB2 for z/OS**.
The catalog schemas differ: LUW uses ``SYSCAT.*``, z/OS uses ``SYSIBM.SYS*``.
The active variant is selected via ``extra_params['db2_platform']`` set to
``"luw"`` (default) or ``"zos"``.
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

_DB2_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="db2")


def _sanitize_error(msg: str) -> str:
    return re.sub(r"(password|passwd|pwd)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)


# Per-platform catalog SQL. The LUW variant uses ``SYSCAT.*``; z/OS exposes the
# same metadata under ``SYSIBM.SYS*`` with slightly different column names.
_CATALOG = {
    "luw": {
        "schemas": (
            "SELECT SCHEMANAME FROM SYSCAT.SCHEMATA "
            "WHERE SCHEMANAME NOT LIKE 'SYS%' AND SCHEMANAME NOT IN ('NULLID','SQLJ') "
            "ORDER BY SCHEMANAME"
        ),
        "schema_exists": "SELECT SCHEMANAME FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = ?",
        "tables": (
            "SELECT TABNAME, CARD, NPAGES * 4096 FROM SYSCAT.TABLES "
            "WHERE TABSCHEMA = ? AND TYPE = 'T' ORDER BY TABNAME"
        ),
        "table_exists": "SELECT TABSCHEMA, TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?",
        "columns": (
            "SELECT COLNAME, TYPENAME, NULLS, LENGTH, SCALE FROM SYSCAT.COLUMNS "
            "WHERE TABSCHEMA = ? AND TABNAME = ? ORDER BY COLNO"
        ),
        "primary_keys": (
            "SELECT kc.COLNAME FROM SYSCAT.TABCONST tc "
            "JOIN SYSCAT.KEYCOLUSE kc ON tc.CONSTNAME = kc.CONSTNAME "
            "AND tc.TABSCHEMA = kc.TABSCHEMA AND tc.TABNAME = kc.TABNAME "
            "WHERE tc.TYPE = 'P' AND tc.TABSCHEMA = ? AND tc.TABNAME = ?"
        ),
        "foreign_keys": (
            "SELECT fk.COLNAME, r.TABSCHEMA, r.TABNAME, pk.COLNAME "
            "FROM SYSCAT.REFERENCES r "
            "JOIN SYSCAT.KEYCOLUSE fk ON fk.CONSTNAME = r.CONSTNAME "
            "JOIN SYSCAT.KEYCOLUSE pk ON pk.CONSTNAME = r.REFKEYNAME "
            "WHERE r.TABSCHEMA = ? AND r.TABNAME = ?"
        ),
    },
    "zos": {
        "schemas": (
            "SELECT DISTINCT CREATOR AS SCHEMANAME FROM SYSIBM.SYSTABLES "
            "WHERE TYPE = 'T' AND CREATOR NOT LIKE 'SYS%' "
            "ORDER BY CREATOR"
        ),
        "schema_exists": (
            "SELECT DISTINCT CREATOR FROM SYSIBM.SYSTABLES WHERE CREATOR = ?"
        ),
        "tables": (
            "SELECT NAME, CARD, NPAGES * 4096 FROM SYSIBM.SYSTABLES "
            "WHERE CREATOR = ? AND TYPE = 'T' ORDER BY NAME"
        ),
        "table_exists": (
            "SELECT CREATOR, NAME FROM SYSIBM.SYSTABLES "
            "WHERE CREATOR = ? AND NAME = ? AND TYPE = 'T'"
        ),
        "columns": (
            "SELECT NAME, COLTYPE, NULLS, LENGTH, SCALE FROM SYSIBM.SYSCOLUMNS "
            "WHERE TBCREATOR = ? AND TBNAME = ? ORDER BY COLNO"
        ),
        "primary_keys": (
            "SELECT k.COLNAME FROM SYSIBM.SYSTABCONST tc "
            "JOIN SYSIBM.SYSKEYCOLUSE k ON tc.CONSTNAME = k.CONSTNAME "
            "WHERE tc.TYPE = 'P' AND tc.TBCREATOR = ? AND tc.TBNAME = ?"
        ),
        "foreign_keys": (
            "SELECT r.COLNAME, r.REFTBCREATOR, r.REFTBNAME, r.REFCOLNAME "
            "FROM SYSIBM.SYSFOREIGNKEYS r "
            "WHERE r.CREATOR = ? AND r.TBNAME = ?"
        ),
    },
}


class DB2Connector(BaseConnector):
    """IBM DB2 connector (LUW + z/OS)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._security = self._extra_params.get("db2_security", "SERVER")  # SERVER, SSL, KERBEROS
        platform = (self._extra_params.get("db2_platform") or "luw").lower()
        if platform not in _CATALOG:
            raise ValueError(f"Unsupported db2_platform '{platform}' — must be 'luw' or 'zos'")
        self._platform = platform
        self._catalog = _CATALOG[platform]
        self._conn = None

    def _build_dsn(self) -> str:
        """Build the DB2 CLI DSN string.

        Auth precedence (most specific wins):
            1. ``kerberos=True`` → AUTHENTICATION=KERBEROS (requires KRB5CCNAME)
            2. ``ldap_enabled=True`` → AUTHENTICATION=LDAP via IBM LDAP plugin
            3. otherwise → standard UID/PWD with optional SSL transport
        """
        parts = [
            f"DATABASE={self._database_name}",
            f"HOSTNAME={self._host}",
            f"PORT={self._port}",
            "PROTOCOL=TCPIP",
        ]

        kerberos = self._extra_params.get("kerberos")
        ldap = self._extra_params.get("ldap_enabled")

        if kerberos:
            # KRBPlugin is the *plugin name* (default IBMkrb5), not the
            # principal — earlier versions of this connector got that wrong
            # and the principal was silently rejected by the driver.
            # The actual principal comes from the OS Kerberos ticket cache
            # (KRB5CCNAME). We surface the principal only for audit logs.
            parts.append("AUTHENTICATION=KERBEROS")
            parts.append(f"KRBPlugin={self._extra_params.get('db2_krb_plugin') or 'IBMkrb5'}")
            if principal := self._extra_params.get("kerberos_principal"):
                parts.append(f"PRINCIPAL={principal}")
        elif ldap:
            # IBM ships an LDAP security plugin; the actual server-side
            # plugin name must match what the DB2 server has enabled
            # (typically ``IBMLDAPauthserver``).
            parts.append("AUTHENTICATION=LDAP")
            parts.append(f"SECURITY={self._extra_params.get('db2_ldap_plugin') or 'IBMLDAPauthserver'}")
            parts.append(f"UID={self._username}")
            parts.append(f"PWD={self._password}")
        else:
            parts.append(f"UID={self._username}")
            parts.append(f"PWD={self._password}")

        # SSL is orthogonal to auth — it's the transport encryption layer.
        if self._extra_params.get("ssl"):
            parts.append("SECURITY=SSL")
            if ca := self._extra_params.get("ssl_ca_cert_path"):
                parts.append(f"SSLServerCertificate={ca}")

        return ";".join(parts) + ";"

    def _connect_sync(self):
        import ibm_db_dbi
        return ibm_db_dbi.connect(self._build_dsn(), "", "")

    def _get_conn_sync(self):
        if self._conn is None:
            self._conn = self._connect_sync()
        return self._conn

    async def _run(self, func, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_DB2_EXECUTOR, func, *args)

    async def test_connection(self) -> bool:
        def _test() -> bool:
            try:
                conn = self._connect_sync()
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
                cur.close()
                conn.close()
                return True
            except Exception as e:
                logger.warning("connector_test_failed", connector="db2", error=_sanitize_error(str(e)))
                return False

        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT + 10):
                return await self._run(_test)
        except Exception:
            return False

    async def get_schemas(self) -> list[dict[str, Any]]:
        allow = local_schemas(self._extra_params)

        def _get() -> list[dict[str, Any]]:
            conn = self._get_conn_sync()
            cur = conn.cursor()
            cur.execute(self._catalog["schemas"])
            schemas = [{"name": r[0].strip()} for r in cur.fetchall()]
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
            cur.execute(self._catalog["tables"], (schema.upper(),))
            tables = [
                {"name": r[0].strip(), "row_count": int(r[1] or 0), "size_bytes": int(r[2] or 0)}
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
            cur.execute(self._catalog["columns"], (schema.upper(), table.upper()))
            cols = cur.fetchall()

            cur.execute(self._catalog["primary_keys"], (schema.upper(), table.upper()))
            pk_cols = {r[0].strip() for r in cur.fetchall()}

            cur.execute(self._catalog["foreign_keys"], (schema.upper(), table.upper()))
            fk_map = {
                r[0].strip(): {"schema": r[1].strip(), "table": r[2].strip(), "column": r[3].strip()}
                for r in cur.fetchall()
            }
            cur.close()

            return [
                {
                    "name": r[0].strip(),
                    "data_type": r[1].strip().lower(),
                    "is_nullable": r[2] == "Y",
                    "character_maximum_length": r[3],
                    "numeric_precision": r[4],
                    "is_primary_key": r[0].strip() in pk_cols,
                    "is_foreign_key": r[0].strip() in fk_map,
                    "fk_references": fk_map.get(r[0].strip()),
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
            cur.execute(f'SELECT * FROM "{vs}"."{vt}" FETCH FIRST {min(limit, 1000)} ROWS ONLY')
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
        cur.execute(self._catalog["schema_exists"], (schema.upper(),))
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Schema '{schema}' does not exist")
        return row[0].strip()

    def _validate_table_sync(self, conn, schema: str, table: str) -> tuple[str, str]:
        cur = conn.cursor()
        cur.execute(self._catalog["table_exists"], (schema.upper(), table.upper()))
        row = cur.fetchone()
        cur.close()
        if row is None:
            raise ValueError(f"Table '{schema}.{table}' does not exist")
        return row[0].strip(), row[1].strip()
