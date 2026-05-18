"""Tests proving edit-save never wipes secrets and metadata never leaks them.

Two failure modes guarded against:
1. Backend ConnectionResponse leaks stored secrets (tokens, keys, passwords).
2. Edit-save submits redacted/empty secrets and the backend overwrites the
   stored values with the empties — wiping enterprise-auth configuration.
"""

from __future__ import annotations

from app.infrastructure.connectors._secrets import (
    SECRET_KEYS,
    is_secret_key,
    merge_preserving_secrets,
    redact,
)


class TestSecretKeyClassification:
    def test_known_keys_marked_secret(self) -> None:
        for key in (
            "access_token",
            "private_key_pem",
            "oauth_refresh_token",
            "oauth_client_secret",
            "azure_ad_token",
            "databricks_client_secret",
            "aws_session_token",
        ):
            assert is_secret_key(key), f"{key!r} must be classified as secret"

    def test_suffix_heuristic_catches_new_keys(self) -> None:
        # Adding a new connector with a foo_token field would be auto-redacted.
        assert is_secret_key("new_thing_token")
        assert is_secret_key("custom_password")
        assert is_secret_key("svc_secret")

    def test_non_secret_keys_pass_through(self) -> None:
        for key in (
            "account",
            "warehouse",
            "role",
            "service_name",
            "http_path",
            "local_schemas",
            "db2_platform",
        ):
            assert not is_secret_key(key), f"{key!r} should not be classified as secret"


class TestRedact:
    def test_handles_none_and_empty(self) -> None:
        assert redact(None) == {}
        assert redact({}) == {}

    def test_redacts_secret_values_only(self) -> None:
        out = redact({
            "account": "abc",
            "private_key_pem": "-----BEGIN PRIVATE KEY-----...",
            "warehouse": "WH",
            "oauth_refresh_token": "rfsh-token-secret",
        })
        assert out["account"] == "abc"
        assert out["warehouse"] == "WH"
        assert out["private_key_pem"] == ""
        assert out["oauth_refresh_token"] == ""

    def test_redact_signals_presence_without_value(self) -> None:
        """Empty-string redaction lets the frontend show 'token is set, leave
        blank to keep' UX while never leaking the value."""
        out = redact({"access_token": "dapi-secret"})
        assert "access_token" in out  # key preserved
        assert out["access_token"] == ""  # value blanked


class TestMergePreservingSecrets:
    def test_empty_secret_preserves_existing(self) -> None:
        existing = {"access_token": "real-token", "http_path": "/sql/1.0/old"}
        incoming = {"access_token": "", "http_path": "/sql/1.0/new"}
        merged = merge_preserving_secrets(existing, incoming)
        assert merged["access_token"] == "real-token"  # not wiped!
        assert merged["http_path"] == "/sql/1.0/new"  # non-secret overwritten

    def test_non_empty_secret_overwrites(self) -> None:
        existing = {"private_key_pem": "old-key"}
        incoming = {"private_key_pem": "new-key-pem"}
        merged = merge_preserving_secrets(existing, incoming)
        assert merged["private_key_pem"] == "new-key-pem"

    def test_missing_secret_in_incoming_keeps_existing(self) -> None:
        existing = {"oauth_refresh_token": "rfsh", "okta_url": "https://x.okta.com"}
        incoming = {"okta_url": "https://y.okta.com"}
        merged = merge_preserving_secrets(existing, incoming)
        assert merged["oauth_refresh_token"] == "rfsh"
        assert merged["okta_url"] == "https://y.okta.com"

    def test_non_secret_can_be_explicitly_dropped_with_none(self) -> None:
        existing = {"local_schemas": ["public"], "warehouse": "WH"}
        incoming = {"local_schemas": None}
        merged = merge_preserving_secrets(existing, incoming)
        assert "local_schemas" not in merged
        assert merged["warehouse"] == "WH"

    def test_handles_none_inputs(self) -> None:
        assert merge_preserving_secrets(None, None) == {}
        assert merge_preserving_secrets({"a": 1}, None) == {"a": 1}
        assert merge_preserving_secrets(None, {"a": 1}) == {"a": 1}

    def test_edit_save_does_not_wipe_snowflake_key_pair(self) -> None:
        """End-to-end scenario: user saved a Snowflake key-pair connection,
        then opens edit drawer and changes only the connection name."""
        stored = {
            "account": "xy12345.us-east-1",
            "warehouse": "COMPUTE_WH",
            "auth_mode": "key_pair",
            "private_key_pem": "-----BEGIN PRIVATE KEY-----...",
            "private_key_passphrase": "hunter2",
        }
        # Frontend renders these as: account="xy...", warehouse="COMPUTE_WH",
        # auth_mode="key_pair", private_key_pem="" (redacted), passphrase=""
        # User changes the connection name only and clicks Save. Frontend
        # rebuilds the payload from the form, which still has the redacted
        # blanks for the two secret fields.
        edit_save = {
            "account": "xy12345.us-east-1",
            "warehouse": "COMPUTE_WH",
            "auth_mode": "key_pair",
            "private_key_pem": "",        # ← redacted blank
            "private_key_passphrase": "",  # ← redacted blank
        }
        merged = merge_preserving_secrets(stored, edit_save)
        assert merged["private_key_pem"] == "-----BEGIN PRIVATE KEY-----..."
        assert merged["private_key_passphrase"] == "hunter2"

    def test_edit_save_does_not_wipe_databricks_m2m(self) -> None:
        stored = {
            "http_path": "/sql/1.0/warehouses/abc",
            "auth_mode": "oauth_m2m",
            "databricks_client_id": "svc-abc",
            "databricks_client_secret": "very-secret",
        }
        edit_save = {
            "http_path": "/sql/1.0/warehouses/abc",
            "auth_mode": "oauth_m2m",
            "databricks_client_id": "svc-abc",
            "databricks_client_secret": "",  # redacted
        }
        merged = merge_preserving_secrets(stored, edit_save)
        assert merged["databricks_client_secret"] == "very-secret"
