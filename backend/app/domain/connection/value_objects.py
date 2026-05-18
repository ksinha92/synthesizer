"""Value objects for the connection bounded context. No framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.domain.shared.value_object import ValueObject


class ConnectorType(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    SNOWFLAKE = "snowflake"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    REDSHIFT = "redshift"
    DATABRICKS = "databricks"
    DB2 = "db2"


class AuthMode(str, Enum):
    """Authentication mode for a connection. Each connector supports a subset."""

    PASSWORD = "password"
    KERBEROS = "kerberos"
    KEY_PAIR = "key_pair"  # Snowflake private key
    OAUTH = "oauth"  # Snowflake externalbrowser / SSO
    IAM = "iam"  # Redshift IAM
    AZURE_AD = "azure_ad"  # SQL Server / Databricks
    TOKEN = "token"  # Databricks personal access token
    SCRAM_SHA_256 = "scram_sha_256"  # MongoDB
    SCRAM_SHA_1 = "scram_sha_1"  # MongoDB
    X509 = "x509"  # MongoDB cert auth
    GSSAPI = "gssapi"  # MongoDB Kerberos
    AWS = "aws"  # MongoDB AWS IAM
    EXTERNALBROWSER = "externalbrowser"  # Snowflake desktop SSO
    OKTA = "okta"  # Snowflake SAML
    OAUTH_M2M = "oauth_m2m"  # Databricks service principal
    WINDOWS = "windows"  # SQL Server Trusted_Connection / Kerberos
    LDAP = "ldap"  # DB2 LDAP plugin


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    FAILED = "failed"
    UNTESTED = "untested"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ConnectionCredentials(ValueObject):
    """Typed container for connection secrets."""

    username: str = ""
    password: str = ""
    extra: dict = field(default_factory=dict)
