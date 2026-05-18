"""Unit tests for the shared SSL / Kerberos / localSchemas helpers."""

from __future__ import annotations

import ssl as ssl_module

from app.infrastructure.connectors._ssl import (
    build_driver_ssl_kwargs,
    build_ssl_context,
    kerberos_enabled,
    kerberos_principal,
    local_schemas,
)


class TestBuildSslContext:
    def test_returns_none_when_ssl_disabled(self) -> None:
        assert build_ssl_context({}) is None
        assert build_ssl_context({"ssl": False}) is None

    def test_returns_context_when_ssl_enabled(self) -> None:
        ctx = build_ssl_context({"ssl": True})
        assert isinstance(ctx, ssl_module.SSLContext)
        assert ctx.check_hostname is True
        assert ctx.verify_mode == ssl_module.CERT_REQUIRED

    def test_trust_server_cert_disables_verification(self) -> None:
        ctx = build_ssl_context({"ssl": True, "ssl_trust_server_cert": True})
        assert ctx is not None
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl_module.CERT_NONE


class TestBuildDriverSslKwargs:
    def test_psycopg_disabled_returns_empty(self) -> None:
        assert build_driver_ssl_kwargs({}, "psycopg") == {}

    def test_psycopg_verify_full_default(self) -> None:
        out = build_driver_ssl_kwargs({"ssl": True}, "psycopg")
        assert out["sslmode"] == "verify-full"

    def test_psycopg_require_when_trusting_server_cert(self) -> None:
        out = build_driver_ssl_kwargs({"ssl": True, "ssl_trust_server_cert": True}, "psycopg")
        assert out["sslmode"] == "require"

    def test_oracle_wallet_passthrough(self) -> None:
        out = build_driver_ssl_kwargs(
            {"ssl": True, "oracle_wallet_path": "/etc/oracle/wallet"},
            "oracle",
        )
        assert out["wallet_location"] == "/etc/oracle/wallet"


class TestKerberosHelpers:
    def test_kerberos_disabled_by_default(self) -> None:
        assert kerberos_enabled({}) is False

    def test_kerberos_enabled_when_truthy(self) -> None:
        assert kerberos_enabled({"kerberos": True}) is True

    def test_principal_returned_or_none(self) -> None:
        assert kerberos_principal({}) is None
        assert kerberos_principal({"kerberos_principal": "u@R"}) == "u@R"


class TestLocalSchemas:
    def test_none_when_missing_or_empty(self) -> None:
        assert local_schemas({}) is None
        assert local_schemas({"local_schemas": ""}) is None
        assert local_schemas({"local_schemas": []}) is None

    def test_csv_string_is_split(self) -> None:
        out = local_schemas({"local_schemas": "public, audit ,billing"})
        assert out == ["public", "audit", "billing"]

    def test_list_passthrough_filters_empty(self) -> None:
        assert local_schemas({"local_schemas": ["a", "", "b"]}) == ["a", "b"]
