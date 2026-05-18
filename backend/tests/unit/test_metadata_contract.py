"""Contract test: every auth mode the UI exposes is reflected in metadata.

Catches the Codex-flagged class of bug where ``CONNECTOR_METADATA`` advertises
fewer auth modes than what the frontend offers — leading to a divergent
``/connections/metadata`` payload that lies about what's supported.

We hardcode the UI auth-mode catalogue here (mirroring the zod enums in
``frontend/src/components/connections/connection-fieldset.tsx``) because the
backend test container does not have the frontend tree mounted. Drift between
the two surfaces is caught by anyone editing one side without the other —
the test breaks at the next CI run.
"""

from __future__ import annotations

import pytest

from app.domain.connection.value_objects import AuthMode
from app.infrastructure.connectors.registry import CONNECTOR_METADATA


# Mirror of the zod enums in connection-fieldset.tsx. Keep in sync when the
# UI gains/loses an option; the test will fail loudly otherwise.
UI_AUTH_MODES_PER_CONNECTOR: dict[str, set[str]] = {
    "snowflake": {"password", "key_pair", "oauth", "okta", "externalbrowser"},
    "oracle": {"password", "kerberos", "azure_ad"},
    "sqlserver": {"password", "azure_ad", "windows"},
    "redshift": {"password", "iam"},
    "databricks": {"token", "oauth_m2m"},
}

# MongoDB's UI uses a *mechanism* selector rather than auth_mode. The mapping
# below maps each UI-offered mechanism to the canonical AuthMode value the
# metadata advertises.
MONGO_MECHANISM_TO_MODE = {
    "SCRAM-SHA-256": "scram_sha_256",
    "SCRAM-SHA-1": "scram_sha_1",
    "MONGODB-X509": "x509",
    "GSSAPI": "gssapi",
    "MONGODB-AWS": "aws",
}
MONGO_UI_MECHANISMS = set(MONGO_MECHANISM_TO_MODE.keys())

# DB2's UI uses a ``db2Security`` enum mixing transport (SSL) and auth modes;
# the auth components map to:
DB2_SECURITY_TO_MODE = {
    "SERVER": "password",
    "KERBEROS": "kerberos",
    "LDAP": "ldap",
    # SSL is transport-only; not an auth_mode.
}


class TestMetadataMatchesUI:
    @pytest.mark.parametrize("connector_type", sorted(UI_AUTH_MODES_PER_CONNECTOR))
    def test_ui_auth_modes_are_advertised_by_metadata(self, connector_type: str) -> None:
        ui_modes = UI_AUTH_MODES_PER_CONNECTOR[connector_type]
        meta_modes = set(CONNECTOR_METADATA[connector_type]["auth_modes"])
        missing = ui_modes - meta_modes
        assert not missing, (
            f"{connector_type}: UI offers auth modes {sorted(missing)} that "
            f"CONNECTOR_METADATA does not advertise. Either add them to the "
            f"metadata or remove them from the UI."
        )

    def test_mongo_advertises_every_mechanism_the_ui_exposes(self) -> None:
        expected = {MONGO_MECHANISM_TO_MODE[m] for m in MONGO_UI_MECHANISMS}
        meta_modes = set(CONNECTOR_METADATA["mongodb"]["auth_modes"])
        missing = expected - meta_modes
        assert not missing, (
            f"MongoDB UI offers mechanisms {sorted(missing)} that the metadata "
            f"doesn't advertise as auth_modes."
        )

    def test_db2_kerberos_and_ldap_advertised(self) -> None:
        meta_modes = set(CONNECTOR_METADATA["db2"]["auth_modes"])
        for security_value in ("KERBEROS", "LDAP"):
            expected_mode = DB2_SECURITY_TO_MODE[security_value]
            assert expected_mode in meta_modes, (
                f"DB2 metadata missing auth_mode {expected_mode!r} (selected "
                f"by UI ``db2Security={security_value}``)."
            )


class TestEveryMetadataModeIsKnown:
    """Every auth_mode in metadata must correspond to an ``AuthMode`` enum
    value — catches typos and stale entries."""

    @pytest.mark.parametrize("connector_type", sorted(CONNECTOR_METADATA))
    def test_all_modes_are_known(self, connector_type: str) -> None:
        meta_modes = set(CONNECTOR_METADATA[connector_type]["auth_modes"])
        known = {m.value for m in AuthMode}
        unknown = meta_modes - known
        assert not unknown, (
            f"{connector_type}: metadata lists unknown auth modes {sorted(unknown)}. "
            f"Add them to AuthMode enum or remove from metadata."
        )


class TestCriticalExtrasListed:
    """Spot-check that the optional_extras catalogue includes every key the
    connector actually reads — the most-likely regression vector."""

    def test_snowflake_oauth_refresh_quad_listed(self) -> None:
        extras = set(CONNECTOR_METADATA["snowflake"]["optional_extras"])
        for key in (
            "oauth_token",
            "oauth_refresh_token",
            "oauth_client_id",
            "oauth_client_secret",
            "oauth_token_endpoint",
            "okta_url",
        ):
            assert key in extras, f"Snowflake metadata missing optional_extra {key!r}"

    def test_databricks_m2m_credentials_listed(self) -> None:
        extras = set(CONNECTOR_METADATA["databricks"]["optional_extras"])
        assert "databricks_client_id" in extras
        assert "databricks_client_secret" in extras

    def test_oracle_azure_ad_token_listed(self) -> None:
        assert "azure_ad_token" in CONNECTOR_METADATA["oracle"]["optional_extras"]

    def test_mongo_enterprise_extras_listed(self) -> None:
        extras = set(CONNECTOR_METADATA["mongodb"]["optional_extras"])
        for key in ("gssapi_service_name", "aws_session_token"):
            assert key in extras

    def test_db2_ldap_extras_listed(self) -> None:
        extras = set(CONNECTOR_METADATA["db2"]["optional_extras"])
        for key in ("ldap_enabled", "db2_ldap_plugin", "db2_krb_plugin"):
            assert key in extras

    def test_sqlserver_azure_ad_extras_listed(self) -> None:
        extras = set(CONNECTOR_METADATA["sqlserver"]["optional_extras"])
        for key in ("azure_ad_token", "pyodbc_driver"):
            assert key in extras
