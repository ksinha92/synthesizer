"""Catalogue of secret keys inside connection ``extra_params``.

Used in two places:

- The connection API response masks these keys before serialising so the
  frontend never sees a stored secret value but DOES see that the key was
  set (rendered as an empty string).
- The UpdateConnectionHandler merges them: if the client submits an empty
  value for one of these keys (or omits the key entirely), the existing
  stored value is preserved. Non-empty values overwrite.

This avoids the "edit-save wipes enterprise auth config" bug — the user
can edit a single field on a connection without re-typing every PAT,
private key, and OAuth client secret they set the first time.
"""

from __future__ import annotations

from typing import Any

SECRET_KEYS: frozenset[str] = frozenset(
    {
        # Snowflake
        "private_key_pem",
        "private_key_passphrase",
        "oauth_token",
        "oauth_refresh_token",
        "oauth_client_secret",
        # Oracle / SQL Server Azure AD
        "azure_ad_token",
        # Databricks
        "access_token",
        "databricks_client_secret",
        # MongoDB
        "aws_session_token",
        # DB2 / others — anything matching the heuristic below
    }
)

# Wildcard heuristic — additionally treat any extra key that ends with one
# of these suffixes as secret. Catches future fields we add to a UI without
# remembering to update the explicit list.
SECRET_SUFFIXES: tuple[str, ...] = (
    "_token",
    "_secret",
    "_password",
    "_passphrase",
    "_private_key",
    "_pem",
)


def is_secret_key(key: str) -> bool:
    if key in SECRET_KEYS:
        return True
    return any(key.endswith(suffix) for suffix in SECRET_SUFFIXES)


def redact(extras: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of ``extras`` with secret values replaced by ``""``.

    Empty string (vs ``None`` or omitting the key) signals to the frontend
    that the secret is set but its value cannot be read back. The form
    treats empty input on save as "preserve existing" via the merge below.
    """
    if not extras:
        return {}
    return {k: ("" if is_secret_key(k) else v) for k, v in extras.items()}


def merge_preserving_secrets(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge ``incoming`` extras over ``existing``, preserving secrets that
    the client sent as empty/missing.

    The merge is one-deep — extras are flat at the API surface so we don't
    need to walk a tree.
    """
    base = dict(existing or {})
    new = dict(incoming or {})

    for key, value in new.items():
        if is_secret_key(key) and (value in ("", None)):
            # Client sent an empty secret value: keep whatever we have stored.
            # If we never stored one either, drop the key entirely so we don't
            # write empty strings into the DB.
            continue
        base[key] = value

    # Allow the client to explicitly drop a non-secret key by sending None.
    for key in list(base):
        if key in new and new[key] is None and not is_secret_key(key):
            del base[key]

    return base
