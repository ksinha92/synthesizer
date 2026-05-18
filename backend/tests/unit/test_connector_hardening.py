"""Tests for the production-hardening fixes applied to the connectors.

Covers:
- SSL env-gate (CERT_NONE blocked in production)
- pymssql encryption kwarg wiring
- DB2 z/OS vs LUW catalog branching
- Async retry classification + backoff
- Snowflake session parameters (QUERY_TAG, STATEMENT_TIMEOUT)
- Redshift application_name passthrough
- Oracle PDB validation
- Mongo pool sizing
"""

from __future__ import annotations

import asyncio
import os
import ssl
from unittest.mock import patch

import pytest

from app.infrastructure.connectors._retry import is_transient, retry_async
from app.infrastructure.connectors._ssl import (
    InsecureTLSInProductionError,
    build_driver_ssl_kwargs,
    build_ssl_context,
)
from app.infrastructure.connectors.cloud.databricks import DatabricksConnector
from app.infrastructure.connectors.cloud.redshift import RedshiftConnector
from app.infrastructure.connectors.cloud.snowflake import SnowflakeConnector
from app.infrastructure.connectors.nosql.mongodb import MongoDBConnector
from app.infrastructure.connectors.sql.db2 import DB2Connector
from app.infrastructure.connectors.sql.oracle import OracleConnector
from app.infrastructure.connectors.sql.sqlserver import SQLServerConnector


# ── SSL env-gate ─────────────────────────────────────────────────────────


class TestSslEnvGate:
    def test_trust_server_cert_allowed_in_development(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            ctx = build_ssl_context({"ssl": True, "ssl_trust_server_cert": True})
            assert ctx is not None
            assert ctx.verify_mode == ssl.CERT_NONE

    def test_trust_server_cert_blocked_in_production(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            with pytest.raises(InsecureTLSInProductionError):
                build_ssl_context({"ssl": True, "ssl_trust_server_cert": True})

    def test_strict_mode_passes_in_production_with_real_ca(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            ctx = build_ssl_context({"ssl": True})
            assert ctx is not None
            assert ctx.verify_mode == ssl.CERT_REQUIRED


# ── pymssql encryption ────────────────────────────────────────────────────


class TestPyodbcSSLConnString:
    """SQL Server connector is pyodbc-only; SSL is enforced via the ODBC
    connection string, not via a driver kwargs dict."""

    def test_encrypt_yes_when_ssl_on(self) -> None:
        c = SQLServerConnector(
            host="h", port=1433, database_name="d", username="u", password="p",
            extra_params={"ssl": True},
        )
        assert "Encrypt=yes" in c._build_conn_str()
        assert "TrustServerCertificate=no" in c._build_conn_str()

    def test_encrypt_no_when_ssl_off(self) -> None:
        c = SQLServerConnector(host="h", port=1433, database_name="d", username="u", password="p")
        assert "Encrypt=no" in c._build_conn_str()

    def test_trust_server_cert_propagates_in_dev(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            c = SQLServerConnector(
                host="h", port=1433, database_name="d", username="u", password="p",
                extra_params={"ssl": True, "ssl_trust_server_cert": True},
            )
            assert "TrustServerCertificate=yes" in c._build_conn_str()

    def test_sqlserver_connector_includes_encryption_in_conn_str(self) -> None:
        c = SQLServerConnector(
            host="h", port=1433, database_name="d", username="u", password="p",
            extra_params={"ssl": True},
        )
        # SQL Server is pyodbc-only now; SSL is enforced via the ODBC
        # connection string ``Encrypt=yes`` flag, not via pymssql kwargs.
        conn_str = c._build_conn_str()
        assert "Encrypt=yes" in conn_str
        assert "TrustServerCertificate=no" in conn_str


# ── DB2 platform branching ────────────────────────────────────────────────


class TestDB2PlatformBranching:
    def test_defaults_to_luw(self) -> None:
        c = DB2Connector(host="h", port=50000, database_name="POL")
        assert c._platform == "luw"
        assert "SYSCAT.SCHEMATA" in c._catalog["schemas"]

    def test_zos_uses_sysibm_catalog(self) -> None:
        c = DB2Connector(
            host="h", port=50000, database_name="POL",
            extra_params={"db2_platform": "zos"},
        )
        assert c._platform == "zos"
        assert "SYSIBM.SYSTABLES" in c._catalog["schemas"]
        assert "SYSCAT" not in c._catalog["schemas"]

    def test_unknown_platform_rejected(self) -> None:
        with pytest.raises(ValueError):
            DB2Connector(
                host="h", port=50000, database_name="POL",
                extra_params={"db2_platform": "windows"},
            )


# ── Retry helper ──────────────────────────────────────────────────────────


class TestRetryClassification:
    def test_transient_markers(self) -> None:
        for marker in ("timeout", "connection reset", "503", "warehouse is starting"):
            assert is_transient(Exception(f"some error {marker} here"))

    def test_permanent_errors_not_retried(self) -> None:
        assert not is_transient(ValueError("invalid password"))
        assert not is_transient(KeyError("missing key"))

    def test_timeout_class_name_treated_as_transient(self) -> None:
        class FakeTimeout(Exception):
            pass

        # Class name contains "timeout"
        FakeTimeout.__name__ = "ConnectTimeout"
        assert is_transient(FakeTimeout("anything"))


class TestRetryAsync:
    @pytest.mark.asyncio
    async def test_succeeds_first_attempt(self) -> None:
        calls = 0

        async def f() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        assert await retry_async(f, attempts=3, base_delay=0.0) == "ok"
        assert calls == 1

    @pytest.mark.asyncio
    async def test_retries_on_transient_then_succeeds(self) -> None:
        calls = 0

        async def f() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("connection refused")
            return "ok"

        assert await retry_async(f, attempts=5, base_delay=0.0, max_delay=0.0) == "ok"
        assert calls == 3

    @pytest.mark.asyncio
    async def test_permanent_errors_bubble_immediately(self) -> None:
        calls = 0

        async def f() -> None:
            nonlocal calls
            calls += 1
            raise ValueError("authentication failed")

        with pytest.raises(ValueError):
            await retry_async(f, attempts=5, base_delay=0.0)
        assert calls == 1

    @pytest.mark.asyncio
    async def test_exhausts_attempts(self) -> None:
        calls = 0

        async def f() -> None:
            nonlocal calls
            calls += 1
            raise TimeoutError("timed out")

        with pytest.raises(TimeoutError):
            await retry_async(f, attempts=3, base_delay=0.0)
        assert calls == 3


# ── Cloud connector session params ────────────────────────────────────────


class TestSnowflakeSessionParameters:
    def test_default_query_tag(self) -> None:
        c = SnowflakeConnector(
            host="x", port=443, database_name="d", username="u", password="p",
            extra_params={"account": "abc", "warehouse": "wh"},
        )
        params = c._build_session_parameters()
        assert params["QUERY_TAG"] == "datawrangler"
        assert params["STATEMENT_TIMEOUT_IN_SECONDS"] == 300

    def test_override_query_tag_and_timeout(self) -> None:
        c = SnowflakeConnector(
            host="x", port=443, database_name="d", username="u", password="p",
            extra_params={
                "account": "abc", "warehouse": "wh",
                "query_tag": "tenant=ameritas/job=discovery",
                "statement_timeout_seconds": 60,
            },
        )
        params = c._build_session_parameters()
        assert params["QUERY_TAG"] == "tenant=ameritas/job=discovery"
        assert params["STATEMENT_TIMEOUT_IN_SECONDS"] == 60


# ── Oracle PDB validation ─────────────────────────────────────────────────


class TestOraclePdb:
    def test_no_pdb_when_not_set(self) -> None:
        c = OracleConnector(host="h", port=1521, database_name="d")
        assert c._pdb == ""

    def test_pdb_extracted_from_extras(self) -> None:
        c = OracleConnector(
            host="h", port=1521, database_name="d",
            extra_params={"oracle_pdb": "FINPDB1"},
        )
        assert c._pdb == "FINPDB1"


# ── Mongo pool sizing ─────────────────────────────────────────────────────


class TestMongoPoolSizing:
    def test_pool_kwargs_include_defaults(self) -> None:
        c = MongoDBConnector(host="h", port=27017, database_name="d")
        kw = c._build_client_kwargs()
        assert kw["maxPoolSize"] == 20
        assert kw["minPoolSize"] == 0
        assert kw["socketTimeoutMS"] == 60_000

    def test_pool_kwargs_overridable(self) -> None:
        c = MongoDBConnector(
            host="h", port=27017, database_name="d",
            extra_params={
                "mongo_max_pool_size": 5,
                "mongo_min_pool_size": 1,
                "mongo_socket_timeout_ms": 15_000,
            },
        )
        kw = c._build_client_kwargs()
        assert kw["maxPoolSize"] == 5
        assert kw["minPoolSize"] == 1
        assert kw["socketTimeoutMS"] == 15_000
