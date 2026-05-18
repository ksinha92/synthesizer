"""Unit tests — 90-day deprecation path for legacy webhook signing.

Pre-v0.9 webhook rows have ``secret_hash`` populated but no
``secret_encrypted`` and ``legacy_signing=True``. F14 keeps these
working for 90 days so receivers have time to switch verification
implementations. During that window the dispatcher:

* Signs the raw body (NOT ``f"{ts}.{body}"``) using ``secret_hash`` as the
  HMAC key — preserving the prior signature contract exactly.
* Adds an ``X-Webhook-Legacy-Signing: true`` header so receivers know
  this delivery is using the deprecated path and can log / nag.
* Still emits ``X-Webhook-Timestamp`` for parity, so the column can be
  populated in logs even though it isn't part of the legacy signature.
"""

from __future__ import annotations

import hashlib
import hmac

from app.infrastructure.webhooks.dispatcher import _sign


class _FakeWebhook:
    def __init__(self, secret_encrypted, secret_hash, legacy_signing):
        self.secret_encrypted = secret_encrypted
        self.secret_hash = secret_hash
        self.legacy_signing = legacy_signing


def test_legacy_path_signs_with_secret_hash_and_emits_header():
    """Legacy rows keep the buggy-but-stable signing path for 90 days.

    The signature is HMAC-SHA256 of the raw body keyed on
    ``secret_hash``. Receivers that were already broken (couldn't
    verify) stay broken — but at least they get the
    ``X-Webhook-Legacy-Signing`` flag so monitoring can surface the
    deprecation.
    """
    secret_hash = hashlib.sha256(b"raw-secret").hexdigest()
    webhook = _FakeWebhook(
        secret_encrypted=None,
        secret_hash=secret_hash,
        legacy_signing=True,
    )

    headers, body = _sign(webhook, "job.completed", {"job_id": "abc"})

    assert headers.get("X-Webhook-Legacy-Signing") == "true"
    assert "X-Webhook-Timestamp" in headers  # still emitted, just not part of legacy sig

    expected = hmac.new(secret_hash.encode(), body, hashlib.sha256).hexdigest()
    assert headers["X-Webhook-Signature"] == f"sha256={expected}"


def test_legacy_signing_disabled_blocks_path():
    """Rows with ``legacy_signing=False`` and no ``secret_encrypted`` are unusable.

    This is the state of a v0.9 webhook whose ``secret_encrypted`` got
    deleted somehow — we'd rather refuse to sign than silently fall back
    to the deprecated path (which would also be undetectable to admins
    since no ``X-Webhook-Legacy-Signing`` header would surface).
    """
    import pytest

    webhook = _FakeWebhook(
        secret_encrypted=None,
        secret_hash=hashlib.sha256(b"x").hexdigest(),
        legacy_signing=False,
    )

    with pytest.raises(ValueError, match="no signing material"):
        _sign(webhook, "job.completed", {"x": 1})


def test_encrypted_secret_overrides_legacy_flag():
    """When both signing materials exist, raw-secret wins.

    Operationally this happens when a legacy row gets rotated to a fresh
    secret: ``secret_encrypted`` gets populated but ``legacy_signing``
    might still be true until the rotation tooling clears it. The
    dispatcher must not emit ``X-Webhook-Legacy-Signing`` if we are
    actually using the new path.
    """
    from cryptography.fernet import Fernet

    from app.config import settings
    from app.infrastructure.security.encryption import encrypt_bytes

    # Set up a real key just for this assertion so encrypt_bytes works.
    settings.FERNET_KEY = Fernet.generate_key().decode()

    raw_secret = b"new-raw-secret"
    webhook = _FakeWebhook(
        secret_encrypted=encrypt_bytes(raw_secret),
        secret_hash=hashlib.sha256(raw_secret).hexdigest(),
        legacy_signing=True,  # stale flag — should be ignored
    )

    headers, _body = _sign(webhook, "job.completed", {"x": 1})

    assert "X-Webhook-Legacy-Signing" not in headers
