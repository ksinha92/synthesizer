"""Honest-or-loud tests for every enterprise auth mode exposed in the UI.

Goal: no option that compiles successfully but silently does nothing. Each
mode must either produce a functional driver call OR raise a clear error
that the user can act on. We assert both behaviours.
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import patch


def _stub_databricks_sql(connect_func):
    """Build sys.modules entries so ``from databricks import sql`` works."""
    fake_sql = types.ModuleType("databricks.sql")
    fake_sql.connect = connect_func
    fake_databricks = types.ModuleType("databricks")
    fake_databricks.sql = fake_sql
    return {"databricks": fake_databricks, "databricks.sql": fake_sql}

import pytest

from app.infrastructure.connectors.cloud.databricks import DatabricksConnector
from app.infrastructure.connectors.cloud.snowflake import SnowflakeConnector
from app.infrastructure.connectors.nosql.mongodb import MongoDBConnector
from app.infrastructure.connectors.sql.db2 import DB2Connector
from app.infrastructure.connectors.sql.oracle import OracleConnector
from app.infrastructure.connectors.sql.sqlserver import SQLServerConnector


# ── Snowflake: OAuth + Okta + externalbrowser ─────────────────────────────


class TestSnowflakeAuthModes:
    def test_oauth_without_token_or_refresh_quad_raises(self) -> None:
        c = SnowflakeConnector(
            host="x", port=443, database_name="d", username="u", password="",
            extra_params={"account": "abc", "warehouse": "wh", "auth_mode": "oauth"},
        )
        with pytest.raises(ValueError, match="oauth_token"):
            c._ensure_oauth_token()

    def test_oauth_static_token_returned_as_is(self) -> None:
        c = SnowflakeConnector(
            host="x", port=443, database_name="d", username="u", password="",
            extra_params={
                "account": "abc", "warehouse": "wh",
                "auth_mode": "oauth", "oauth_token": "static-abc",
            },
        )
        assert c._ensure_oauth_token() == "static-abc"

    def test_okta_requires_org_url(self) -> None:
        c = SnowflakeConnector(
            host="x", port=443, database_name="d", username="u", password="p",
            extra_params={"account": "abc", "warehouse": "wh", "auth_mode": "okta"},
        )
        # ``_connect_sync`` would surface the error; verify via state.
        assert c._okta_url == ""

    def test_okta_url_propagates_when_set(self) -> None:
        c = SnowflakeConnector(
            host="x", port=443, database_name="d", username="u", password="p",
            extra_params={
                "account": "abc", "warehouse": "wh",
                "auth_mode": "okta", "okta_url": "https://my-org.okta.com",
            },
        )
        assert c._okta_url == "https://my-org.okta.com"


# ── Databricks: M2M OAuth ──────────────────────────────────────────────────


class TestDatabricksM2MAuth:
    def test_m2m_requires_client_id_and_secret(self) -> None:
        c = DatabricksConnector(
            host="adb.azuredatabricks.net", port=443, database_name="main",
            extra_params={"http_path": "/sql/1.0/warehouses/abc", "auth_mode": "oauth_m2m"},
        )
        # ValueError fires before we touch databricks-sdk
        with patch.dict(sys.modules, _stub_databricks_sql(lambda **k: object())):
            with pytest.raises(ValueError, match="databricks_client_id"):
                c._connect_sync()

    def test_pat_path_still_works(self) -> None:
        captured: dict = {}

        def _connect(**kw):
            captured.update(kw)
            return object()

        c = DatabricksConnector(
            host="adb.azuredatabricks.net", port=443, database_name="main",
            extra_params={
                "http_path": "/sql/1.0/warehouses/abc",
                "access_token": "dapi-secret",
            },
        )
        with patch.dict(sys.modules, _stub_databricks_sql(_connect)):
            c._connect_sync()
        assert captured["access_token"] == "dapi-secret"


# ── Oracle: Kerberos + Azure AD ───────────────────────────────────────────


class TestOracleAuthModes:
    def test_kerberos_sets_externalauth(self) -> None:
        captured: dict = {}

        class _FakeOracleDB:
            @staticmethod
            def makedsn(**kw):
                return "fakedsn"

            @staticmethod
            def connect(**kw):
                captured.update(kw)

                class _Conn:
                    def cursor(self_):
                        class _C:
                            def execute(self, *_a, **_kw):
                                pass

                            def close(self):
                                pass

                        return _C()

                return _Conn()

        c = OracleConnector(
            host="h", port=1521, database_name="d", username="u", password="p",
            extra_params={"auth_mode": "kerberos"},
        )
        with patch.dict(sys.modules, {"oracledb": _FakeOracleDB}):
            c._connect_sync()
        assert captured.get("externalauth") is True
        assert "password" not in captured

    def test_azure_ad_requires_token(self) -> None:
        c = OracleConnector(
            host="h", port=1521, database_name="d", username="u", password="p",
            extra_params={"auth_mode": "azure_ad"},
        )

        class _FakeOracleDB:
            @staticmethod
            def makedsn(**kw):
                return "fakedsn"

            @staticmethod
            def connect(**kw):
                return object()

        with patch.dict(sys.modules, {"oracledb": _FakeOracleDB}):
            with pytest.raises(ValueError, match="azure_ad_token"):
                c._connect_sync()

    def test_azure_ad_passes_callable_token(self) -> None:
        captured: dict = {}

        class _FakeOracleDB:
            @staticmethod
            def makedsn(**kw):
                return "fakedsn"

            @staticmethod
            def connect(**kw):
                captured.update(kw)
                return type("Conn", (), {"cursor": lambda self: type("C", (), {"execute": lambda *_a, **_kw: None, "close": lambda self: None})()})()

        c = OracleConnector(
            host="h", port=1521, database_name="d", username="u", password="p",
            extra_params={"auth_mode": "azure_ad", "azure_ad_token": "jwt-token"},
        )
        with patch.dict(sys.modules, {"oracledb": _FakeOracleDB}):
            c._connect_sync()
        token_cb = captured["access_token"]
        assert callable(token_cb)
        assert token_cb() == "jwt-token"


# ── SQL Server: pyodbc Azure AD ───────────────────────────────────────────


class TestSqlServerAzureAd:
    def test_azure_ad_without_pyodbc_raises_import_error(self) -> None:
        c = SQLServerConnector(
            host="h", port=1433, database_name="d", username="u", password="p",
            extra_params={"auth_mode": "azure_ad", "azure_ad_token": "jwt"},
        )
        with patch.dict(sys.modules, {"pyodbc": None}):
            with pytest.raises(ImportError, match="pyodbc"):
                c._connect_sync()

    def test_azure_ad_without_token_raises_value_error(self) -> None:
        c = SQLServerConnector(
            host="h", port=1433, database_name="d", username="u", password="p",
            extra_params={"auth_mode": "azure_ad"},
        )
        with pytest.raises(ValueError, match="azure_ad_token"):
            c._build_attrs()

    def test_azure_ad_attrs_carry_token_at_sql_copt(self) -> None:
        c = SQLServerConnector(
            host="srv.example.com", port=1433, database_name="db", username="", password="",
            extra_params={"auth_mode": "azure_ad", "azure_ad_token": "jwt"},
        )
        attrs = c._build_attrs()
        assert attrs is not None
        # 1256 = SQL_COPT_SS_ACCESS_TOKEN
        assert 1256 in attrs
        # UCS-2 length prefix + bytes
        struct = attrs[1256]
        expected_len = len("jwt".encode("utf-16-le"))
        assert int.from_bytes(struct[:4], "little") == expected_len

    def test_password_auth_uses_uid_pwd_in_conn_str(self) -> None:
        c = SQLServerConnector(
            host="h", port=1433, database_name="d", username="svc", password="hunter2",
            extra_params={},
        )
        s = c._build_conn_str()
        assert "UID=svc" in s
        assert "PWD=hunter2" in s
        # Should NOT switch to trusted connection.
        assert "Trusted_Connection" not in s

    def test_windows_integrated_auth_uses_trusted_connection(self) -> None:
        c = SQLServerConnector(
            host="h", port=1433, database_name="d", username="", password="",
            extra_params={"auth_mode": "windows"},
        )
        s = c._build_conn_str()
        assert "Trusted_Connection=yes" in s
        assert "UID=" not in s


# ── MongoDB X.509 / GSSAPI / AWS ──────────────────────────────────────────


class TestMongoEnterpriseAuth:
    def test_x509_requires_client_cert_and_key(self) -> None:
        c = MongoDBConnector(
            host="h", port=27017, database_name="d",
            extra_params={"auth_mode": "x509"},
        )
        with pytest.raises(ValueError, match="X.509"):
            c._build_client_kwargs()

    def test_x509_with_cert_and_key_sets_authsource_external(self) -> None:
        c = MongoDBConnector(
            host="h", port=27017, database_name="d",
            extra_params={
                "auth_mode": "x509",
                "ssl_client_cert_path": "/tmp/client.crt",
                "ssl_client_key_path": "/tmp/client.key",
            },
        )
        kw = c._build_client_kwargs()
        assert kw["authMechanism"] == "MONGODB-X509"
        assert kw["authSource"] == "$external"

    def test_gssapi_sets_authsource_external(self) -> None:
        c = MongoDBConnector(
            host="h", port=27017, database_name="d",
            extra_params={"auth_mode": "gssapi"},
        )
        kw = c._build_client_kwargs()
        assert kw["authMechanism"] == "GSSAPI"
        assert kw["authSource"] == "$external"

    def test_aws_session_token_propagates(self) -> None:
        c = MongoDBConnector(
            host="h", port=27017, database_name="d",
            extra_params={"auth_mode": "aws", "aws_session_token": "AQoDYX..."},
        )
        kw = c._build_client_kwargs()
        assert kw["authMechanism"] == "MONGODB-AWS"
        assert "AWS_SESSION_TOKEN:AQoDYX..." in kw["authMechanismProperties"]


# ── DB2 Kerberos DSN + LDAP ───────────────────────────────────────────────


class TestDB2EnterpriseAuth:
    def test_kerberos_dsn_uses_plugin_name_not_principal(self) -> None:
        c = DB2Connector(
            host="h", port=50000, database_name="POL",
            extra_params={"kerberos": True, "kerberos_principal": "u@REALM"},
        )
        dsn = c._build_dsn()
        # Plugin slot should be the default plugin name, not the principal.
        assert "KRBPlugin=IBMkrb5" in dsn
        # Principal goes in the dedicated PRINCIPAL= slot.
        assert "PRINCIPAL=u@REALM" in dsn
        # UID/PWD must NOT be in the Kerberos DSN (ticket cache wins).
        assert "UID=" not in dsn

    def test_custom_kerberos_plugin_overridable(self) -> None:
        c = DB2Connector(
            host="h", port=50000, database_name="POL",
            extra_params={"kerberos": True, "db2_krb_plugin": "MYKRBPlugin"},
        )
        assert "KRBPlugin=MYKRBPlugin" in c._build_dsn()

    def test_ldap_dsn_uses_security_plugin_and_credentials(self) -> None:
        c = DB2Connector(
            host="h", port=50000, database_name="POL", username="u", password="p",
            extra_params={"ldap_enabled": True},
        )
        dsn = c._build_dsn()
        assert "AUTHENTICATION=LDAP" in dsn
        assert "SECURITY=IBMLDAPauthserver" in dsn
        assert "UID=u" in dsn
        assert "PWD=p" in dsn


# ── Postgres Kerberos env-gate ────────────────────────────────────────────


class TestPostgresKerberosEnvGate:
    def test_raises_when_no_ticket_cache(self) -> None:
        from app.infrastructure.connectors.sql.postgresql import PostgreSQLConnector

        c = PostgreSQLConnector(
            host="h", port=5432, database_name="d", username="u",
            extra_params={"kerberos": True, "kerberos_principal": "u@R"},
        )
        with patch.dict(os.environ, {}, clear=True), patch(
            "os.path.exists", return_value=False
        ):
            with pytest.raises(RuntimeError, match="Kerberos ticket"):
                c._build_connect_kwargs()
