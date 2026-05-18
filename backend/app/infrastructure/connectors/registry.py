"""Connector registry — resolves connector classes by type."""

from __future__ import annotations

from typing import Any

from app.domain.connection.value_objects import ConnectorType
from app.domain.shared.errors import NotFoundError
from app.infrastructure.connectors.base import BaseConnector


class ConnectorRegistry:
    """Maps ConnectorType to connector classes. Instantiates on demand."""

    def __init__(self) -> None:
        self._connectors: dict[ConnectorType, type[BaseConnector]] = {}

    def register(self, connector_type: ConnectorType, connector_class: type[BaseConnector]) -> None:
        self._connectors[connector_type] = connector_class

    def get_connector(
        self,
        connector_type: ConnectorType,
        host: str,
        port: int,
        database_name: str,
        username: str = "",
        password: str = "",
        extra_params: dict[str, Any] | None = None,
    ) -> BaseConnector:
        cls = self._connectors.get(connector_type)
        if cls is None:
            raise NotFoundError(
                message=f"No connector registered for type: {connector_type.value}",
                code="connector_not_found",
            )
        return cls(
            host=host,
            port=port,
            database_name=database_name,
            username=username,
            password=password,
            extra_params=extra_params,
        )

    @property
    def registered_types(self) -> list[ConnectorType]:
        return list(self._connectors.keys())


def create_registry() -> ConnectorRegistry:
    """Create registry with all built-in connectors registered."""
    from app.infrastructure.connectors.sql.postgresql import PostgreSQLConnector
    from app.infrastructure.connectors.sql.mysql import MySQLConnector
    from app.infrastructure.connectors.sql.oracle import OracleConnector
    from app.infrastructure.connectors.sql.sqlserver import SQLServerConnector
    from app.infrastructure.connectors.sql.db2 import DB2Connector
    from app.infrastructure.connectors.nosql.mongodb import MongoDBConnector
    from app.infrastructure.connectors.cloud.snowflake import SnowflakeConnector
    from app.infrastructure.connectors.cloud.redshift import RedshiftConnector
    from app.infrastructure.connectors.cloud.databricks import DatabricksConnector

    registry = ConnectorRegistry()
    registry.register(ConnectorType.POSTGRESQL, PostgreSQLConnector)
    registry.register(ConnectorType.MYSQL, MySQLConnector)
    registry.register(ConnectorType.MONGODB, MongoDBConnector)
    registry.register(ConnectorType.SNOWFLAKE, SnowflakeConnector)
    registry.register(ConnectorType.ORACLE, OracleConnector)
    registry.register(ConnectorType.SQLSERVER, SQLServerConnector)
    registry.register(ConnectorType.REDSHIFT, RedshiftConnector)
    registry.register(ConnectorType.DATABRICKS, DatabricksConnector)
    registry.register(ConnectorType.DB2, DB2Connector)
    return registry


# Connector-type metadata for the UI and validators.
#
# Single source of truth for per-connector defaults, required fields, and
# supported auth modes — both the frontend tile grid and the backend
# preflight checks read from this map.
#
# **Contract invariant**: every auth mode listed here MUST be backed by a
# functional code path in the connector. Every key listed in ``required_extras``
# / ``optional_extras`` MUST be read by the connector class. The contract test
# in ``tests/unit/test_metadata_contract.py`` enforces parity with the UI.
CONNECTOR_METADATA: dict[str, dict[str, Any]] = {
    "postgresql": {
        "label": "PostgreSQL",
        "category": "application_db",
        "default_port": 5432,
        "supports_ssl": True,
        "supports_kerberos": True,
        "auth_modes": ["password", "kerberos"],
        "required_extras": [],
        "optional_extras": [
            "local_schemas",
            "ssl_ca_cert_path",
            "ssl_ca_cert_pem",
            "ssl_client_cert_path",
            "ssl_client_key_path",
            "ssl_trust_server_cert",
            "kerberos",
            "kerberos_principal",
            "krb_service_name",
            "block_on_schema_change",
        ],
    },
    "mysql": {
        "label": "MySQL",
        "category": "application_db",
        "default_port": 3306,
        "supports_ssl": True,
        "supports_kerberos": False,
        "auth_modes": ["password"],
        "required_extras": [],
        "optional_extras": [
            "local_schemas",
            "ssl_ca_cert_path",
            "ssl_ca_cert_pem",
            "ssl_client_cert_path",
            "ssl_client_key_path",
            "ssl_trust_server_cert",
            "charset",
            "auth_plugin",
            "block_on_schema_change",
        ],
    },
    "mongodb": {
        "label": "MongoDB",
        "category": "application_db",
        "default_port": 27017,
        "supports_ssl": True,
        "supports_kerberos": True,  # via GSSAPI mechanism
        "auth_modes": [
            "password",
            "scram_sha_256",
            "scram_sha_1",
            "x509",
            "gssapi",
            "aws",
        ],
        "required_extras": [],
        "optional_extras": [
            "auth_mechanism",
            "auth_source",
            "replica_set",
            "max_doc_depth",
            "max_sample_size",
            "ssl_ca_cert_path",
            "ssl_client_cert_path",
            "ssl_client_key_path",
            "ssl_trust_server_cert",
            "gssapi_service_name",
            "aws_session_token",
            "mongo_max_pool_size",
            "mongo_min_pool_size",
            "mongo_socket_timeout_ms",
            "mongo_connect_timeout_ms",
        ],
    },
    "snowflake": {
        "label": "Snowflake",
        "category": "warehouse",
        "default_port": 443,
        "supports_ssl": True,
        "supports_kerberos": False,
        "auth_modes": ["password", "key_pair", "oauth", "okta", "externalbrowser"],
        "required_extras": ["account", "warehouse"],
        "optional_extras": [
            "role",
            "private_key_pem",
            "private_key_passphrase",
            "oauth_token",
            "oauth_refresh_token",
            "oauth_client_id",
            "oauth_client_secret",
            "oauth_token_endpoint",
            "okta_url",
            "query_tag",
            "statement_timeout_seconds",
            "session_parameters",
        ],
    },
    "oracle": {
        "label": "Oracle",
        "category": "application_db",
        "default_port": 1521,
        "supports_ssl": True,
        "supports_kerberos": True,  # via externalauth
        "auth_modes": ["password", "kerberos", "azure_ad"],
        "required_extras": [],
        "optional_extras": [
            "service_name",
            "oracle_pdb",
            "oracle_wallet_path",
            "azure_ad_token",
            "local_schemas",
            "ssl_trust_server_cert",
        ],
    },
    "sqlserver": {
        "label": "SQL Server",
        "category": "application_db",
        "default_port": 1433,
        "supports_ssl": True,
        "supports_kerberos": True,  # via windows/Trusted_Connection
        # All three modes are pyodbc-backed; msodbcsql18 must exist in the
        # worker image. The connector raises ImportError up-front if it's
        # missing — no silent password downgrade.
        "auth_modes": ["password", "azure_ad", "windows"],
        "required_extras": [],
        "optional_extras": [
            "instance",
            "local_schemas",
            "azure_ad_token",
            "pyodbc_driver",
            "ssl_trust_server_cert",
        ],
    },
    "redshift": {
        "label": "Redshift",
        "category": "warehouse",
        "default_port": 5439,
        "supports_ssl": True,
        "supports_kerberos": False,
        "auth_modes": ["password", "iam"],
        "required_extras": [],
        "optional_extras": [
            "iam_cluster_id",
            "iam_db_user",
            "aws_region",
            "application_name",
            "local_schemas",
            "ssl_trust_server_cert",
        ],
    },
    "databricks": {
        "label": "Databricks",
        "category": "warehouse",
        "default_port": 443,
        "supports_ssl": True,
        "supports_kerberos": False,
        "auth_modes": ["token", "oauth_m2m"],
        # ``access_token`` is required only when auth_mode=token; the M2M
        # path needs ``databricks_client_id`` + ``databricks_client_secret``
        # instead. We can't express conditional-required in this flat dict,
        # so http_path stays the only universal required extra and the per-
        # auth-mode check lives in the connector itself.
        "required_extras": ["http_path"],
        "optional_extras": [
            "access_token",
            "databricks_client_id",
            "databricks_client_secret",
            "local_schemas",
            "retry_attempts",
            "retry_delay_min",
            "retry_delay_max",
            "socket_timeout_ms",
        ],
    },
    "db2": {
        "label": "IBM DB2",
        "category": "application_db",
        "default_port": 50000,
        "supports_ssl": True,
        "supports_kerberos": True,
        # ``ldap`` is selected via ``db2_security=LDAP`` + ``ldap_enabled=True``;
        # ``kerberos`` via the standard ``kerberos`` boolean. Listed here so
        # consumers of /metadata know both flows are available.
        "auth_modes": ["password", "kerberos", "ldap"],
        "required_extras": [],
        "optional_extras": [
            "db2_security",
            "db2_platform",
            "db2_krb_plugin",
            "db2_ldap_plugin",
            "ldap_enabled",
            "kerberos",
            "kerberos_principal",
            "ssl_ca_cert_path",
            "local_schemas",
        ],
    },
}
