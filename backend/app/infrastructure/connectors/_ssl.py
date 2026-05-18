"""Shared SSL/TLS helpers for connectors.

Translates the UI's ``ssl`` / ``ssl_trust_server_cert`` / ``ssl_ca_cert``
flags from ``extra_params`` into a Python :class:`ssl.SSLContext` that drivers
that accept one can use directly.

Drivers that take individual param names (``sslmode``, ``ssl_ca``, etc.) build
their own kwargs via :func:`build_driver_ssl_kwargs`.

**Production safety**: ``ssl_trust_server_cert`` (which sets ``CERT_NONE``) is
refused in production. The flag exists for non-prod environments where users
hit self-signed test databases. Allowing it in prod silently turns SSL into
"obfuscated cleartext" — every cert is trusted, including a MITM's.
"""

from __future__ import annotations

import os
import ssl
from typing import Any

import structlog

logger = structlog.get_logger()


class InsecureTLSInProductionError(ValueError):
    """Raised when ``ssl_trust_server_cert`` is used in production."""


def _is_production() -> bool:
    """Read the runtime environment without importing the full Settings object.

    We can't ``from app.config import settings`` here because connectors are
    instantiated from places (Celery tasks, background workers) where the
    settings object may not be initialised. Reading the env var directly is
    cheap and consistent with the rest of the infra layer.
    """
    return os.environ.get("ENVIRONMENT", "development").lower() == "production"


def _trust_server_cert_allowed(extra_params: dict[str, Any]) -> bool:
    """Return True only if the user asked for it AND env permits it."""
    if not extra_params.get("ssl_trust_server_cert"):
        return False
    if _is_production():
        logger.warning(
            "ssl_trust_server_cert_blocked_in_production",
            reason="CERT_NONE refused — supply ssl_ca_cert_path or disable ssl_trust_server_cert",
        )
        raise InsecureTLSInProductionError(
            "ssl_trust_server_cert cannot be used in production. "
            "Provide ssl_ca_cert_path / ssl_ca_cert_pem instead."
        )
    return True


def build_ssl_context(extra_params: dict[str, Any]) -> ssl.SSLContext | None:
    """Return an :class:`ssl.SSLContext` for the given extra_params, or None."""
    if not extra_params.get("ssl"):
        return None

    ctx = ssl.create_default_context()

    if _trust_server_cert_allowed(extra_params):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    elif ca_cert := extra_params.get("ssl_ca_cert_path"):
        ctx.load_verify_locations(cafile=ca_cert)
    elif ca_cert_pem := extra_params.get("ssl_ca_cert_pem"):
        ctx.load_verify_locations(cadata=ca_cert_pem)

    if (client_cert := extra_params.get("ssl_client_cert_path")) and (
        client_key := extra_params.get("ssl_client_key_path")
    ):
        ctx.load_cert_chain(certfile=client_cert, keyfile=client_key)

    return ctx


def build_driver_ssl_kwargs(extra_params: dict[str, Any], driver: str) -> dict[str, Any]:
    """Return driver-specific SSL kwargs derived from extra_params.

    Supported drivers:
        - ``psycopg`` (libpq): sslmode, sslrootcert, sslcert, sslkey
        - ``pymysql`` (aiomysql): ssl kwarg as dict
        - ``pymssql``: encryption='require'|'strict'; trust handled separately
        - ``oracle``: ssl_server_dn_match + wallet_location
    """
    if not extra_params.get("ssl"):
        return {}

    if driver == "psycopg":
        kwargs: dict[str, Any] = {}
        if _trust_server_cert_allowed(extra_params):
            kwargs["sslmode"] = "require"
        else:
            kwargs["sslmode"] = "verify-full"
            if ca := extra_params.get("ssl_ca_cert_path"):
                kwargs["sslrootcert"] = ca
        if cert := extra_params.get("ssl_client_cert_path"):
            kwargs["sslcert"] = cert
        if key := extra_params.get("ssl_client_key_path"):
            kwargs["sslkey"] = key
        return kwargs

    if driver == "pymysql":
        ctx = build_ssl_context(extra_params)
        return {"ssl": ctx} if ctx else {}

    if driver == "pymssql":
        # pymssql 2.2+ exposes ``encryption=`` directly. ``strict`` enforces
        # certificate validation; ``require`` allows self-signed (only when
        # env permits via the trust-server-cert flag).
        if _trust_server_cert_allowed(extra_params):
            return {"encryption": "require"}
        return {"encryption": "strict"}

    if driver == "oracle":
        kwargs = {}
        if wallet := extra_params.get("oracle_wallet_path"):
            kwargs["wallet_location"] = wallet
        if not _trust_server_cert_allowed(extra_params):
            kwargs["ssl_server_dn_match"] = True
        return kwargs

    return {}


def kerberos_enabled(extra_params: dict[str, Any]) -> bool:
    return bool(extra_params.get("kerberos"))


def kerberos_principal(extra_params: dict[str, Any]) -> str | None:
    return extra_params.get("kerberos_principal")


def local_schemas(extra_params: dict[str, Any]) -> list[str] | None:
    """Return the UI ``local_schemas`` list or None for 'all'."""
    val = extra_params.get("local_schemas")
    if not val:
        return None
    if isinstance(val, list):
        return [s for s in val if s]
    if isinstance(val, str):
        return [s.strip() for s in val.split(",") if s.strip()]
    return None
