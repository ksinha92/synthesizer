"""Verify the 5 new connectors correctly hoist params out of extra_params.

These tests don't establish real driver connections — we only verify that
the connector class stores the right state so that when the driver is
called, it gets the right arguments. End-to-end driver tests run inside
the docker-compose integration suite.
"""

from __future__ import annotations

import pytest

from app.infrastructure.connectors.cloud.databricks import DatabricksConnector
from app.infrastructure.connectors.cloud.redshift import RedshiftConnector
from app.infrastructure.connectors.sql.db2 import DB2Connector
from app.infrastructure.connectors.sql.oracle import OracleConnector
from app.infrastructure.connectors.sql.sqlserver import SQLServerConnector


class TestOracleConnector:
    def test_service_name_extracted(self) -> None:
        c = OracleConnector(
            host="h", port=1521, database_name="d", username="u", password="p",
            extra_params={"service_name": "ORCLPDB1"},
        )
        assert c._service_name == "ORCLPDB1"

    def test_defaults_to_empty_service_name(self) -> None:
        c = OracleConnector(host="h", port=1521, database_name="d")
        assert c._service_name == ""


class TestSQLServerConnector:
    def test_instance_extracted(self) -> None:
        c = SQLServerConnector(
            host="h", port=1433, database_name="d", username="u", password="p",
            extra_params={"instance": "SQLEXPRESS"},
        )
        assert c._instance == "SQLEXPRESS"

    def test_ssl_flag_propagates_via_conn_str(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            c = SQLServerConnector(
                host="h", port=1433, database_name="d",
                extra_params={"ssl": True, "ssl_trust_server_cert": True},
            )
            assert c._encrypt is True
            assert c._trust_server_cert is True
            s = c._build_conn_str()
            assert "Encrypt=yes" in s
            assert "TrustServerCertificate=yes" in s


class TestRedshiftConnector:
    def test_iam_auth_state(self) -> None:
        c = RedshiftConnector(
            host="h", port=5439, database_name="d",
            extra_params={
                "auth_mode": "iam",
                "iam_cluster_id": "warehouse-1",
                "iam_db_user": "analyst",
                "aws_region": "us-west-2",
            },
        )
        assert c._auth_mode == "iam"
        assert c._iam_cluster_id == "warehouse-1"
        assert c._iam_db_user == "analyst"
        assert c._aws_region == "us-west-2"

    def test_password_auth_default(self) -> None:
        c = RedshiftConnector(host="h", port=5439, database_name="d")
        assert c._auth_mode == "password"


class TestDatabricksConnector:
    def test_http_path_and_token_extracted(self) -> None:
        c = DatabricksConnector(
            host="adb-1.azuredatabricks.net", port=443, database_name="main",
            extra_params={
                "http_path": "/sql/1.0/warehouses/abc",
                "access_token": "dapi-secret",
            },
        )
        assert c._http_path == "/sql/1.0/warehouses/abc"
        assert c._access_token == "dapi-secret"
        assert c._catalog == "main"

    def test_falls_back_to_password_when_no_access_token(self) -> None:
        c = DatabricksConnector(
            host="h", port=443, database_name="main", password="pat-via-password",
            extra_params={"http_path": "/sql/1.0/warehouses/abc"},
        )
        assert c._access_token == "pat-via-password"


class TestDB2Connector:
    def test_dsn_contains_required_parts(self) -> None:
        c = DB2Connector(host="h", port=50000, database_name="POL", username="u", password="p")
        dsn = c._build_dsn()
        assert "DATABASE=POL" in dsn
        assert "HOSTNAME=h" in dsn
        assert "PORT=50000" in dsn
        assert "UID=u" in dsn

    def test_dsn_includes_ssl_when_enabled(self) -> None:
        c = DB2Connector(
            host="h", port=50000, database_name="POL",
            extra_params={"ssl": True, "ssl_ca_cert_path": "/etc/ssl/ca.crt"},
        )
        dsn = c._build_dsn()
        assert "SECURITY=SSL" in dsn
        assert "SSLServerCertificate=/etc/ssl/ca.crt" in dsn

    def test_dsn_includes_kerberos_when_enabled(self) -> None:
        c = DB2Connector(
            host="h", port=50000, database_name="POL",
            extra_params={"kerberos": True, "kerberos_principal": "u@REALM"},
        )
        dsn = c._build_dsn()
        assert "AUTHENTICATION=KERBEROS" in dsn
