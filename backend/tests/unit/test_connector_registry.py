"""Unit tests for the connector registry — verifies all 9 connector types
are registered, the metadata catalogue is complete, and unknown types raise
NotFoundError instead of silently returning None.

We do not exercise driver-level behaviour here (mocked separately per-
connector) — this is the contract layer.
"""

from __future__ import annotations

import pytest

from app.domain.connection.value_objects import AuthMode, ConnectorType
from app.domain.shared.errors import NotFoundError
from app.infrastructure.connectors.registry import (
    CONNECTOR_METADATA,
    ConnectorRegistry,
    create_registry,
)


EXPECTED_TYPES = {
    ConnectorType.POSTGRESQL,
    ConnectorType.MYSQL,
    ConnectorType.MONGODB,
    ConnectorType.SNOWFLAKE,
    ConnectorType.ORACLE,
    ConnectorType.SQLSERVER,
    ConnectorType.REDSHIFT,
    ConnectorType.DATABRICKS,
    ConnectorType.DB2,
}


class TestConnectorRegistry:
    def test_all_nine_connectors_registered(self) -> None:
        registry = create_registry()
        assert set(registry.registered_types) == EXPECTED_TYPES

    def test_metadata_covers_every_registered_type(self) -> None:
        registry = create_registry()
        meta_types = {ConnectorType(k) for k in CONNECTOR_METADATA}
        assert meta_types == set(registry.registered_types)

    def test_unknown_connector_raises(self) -> None:
        registry = ConnectorRegistry()
        with pytest.raises(NotFoundError):
            registry.get_connector(
                connector_type=ConnectorType.POSTGRESQL,
                host="x",
                port=1,
                database_name="x",
            )

    @pytest.mark.parametrize("connector_type", sorted(EXPECTED_TYPES, key=lambda t: t.value))
    def test_metadata_shape(self, connector_type: ConnectorType) -> None:
        meta = CONNECTOR_METADATA[connector_type.value]
        assert meta["label"]
        assert meta["category"] in {"application_db", "warehouse", "file"}
        assert 1 <= meta["default_port"] <= 65535
        assert "auth_modes" in meta and meta["auth_modes"]
        for mode in meta["auth_modes"]:
            assert mode in {m.value for m in AuthMode}, f"Unknown auth mode {mode}"

    def test_snowflake_metadata_has_key_pair_auth(self) -> None:
        assert "key_pair" in CONNECTOR_METADATA["snowflake"]["auth_modes"]

    def test_databricks_requires_http_path(self) -> None:
        # ``access_token`` moved to optional_extras because the M2M OAuth
        # path uses client_id/secret instead. The per-auth-mode requirement
        # is enforced inside DatabricksConnector._connect_sync, not via
        # this metadata block (which can't express "required for mode X").
        required = CONNECTOR_METADATA["databricks"]["required_extras"]
        optional = CONNECTOR_METADATA["databricks"]["optional_extras"]
        assert "http_path" in required
        assert "access_token" in optional
        assert "databricks_client_id" in optional
        assert "databricks_client_secret" in optional

    def test_db2_supports_kerberos(self) -> None:
        assert CONNECTOR_METADATA["db2"]["supports_kerberos"] is True
