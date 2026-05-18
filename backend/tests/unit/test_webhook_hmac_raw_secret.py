"""Unit tests — webhook HMAC keyed on the raw secret (Phase 60 F14).

The dispatcher's prior signing path used ``secret_hash`` (sha256 of the
raw secret) as the HMAC key. Receivers who held the raw secret returned
at webhook creation could never reproduce that, so the signature header
was effectively decorative. The fix is to:

1. Store the raw secret Fernet-encrypted on the webhook row.
2. Decrypt at dispatch time and HMAC over ``f"{ts}.{body}"`` with the
   raw secret as the key.
3. Emit ``X-Webhook-Timestamp`` so receivers can apply a skew window.

These tests construct a webhook with ``secret_encrypted=encrypt(secret)``,
dispatch a payload, and confirm a receiver-side HMAC over
``f"{ts}.{body}"`` with the raw secret matches the
``X-Webhook-Signature`` header.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.infrastructure.security.encryption import encrypt_bytes
from app.infrastructure.webhooks.dispatcher import _sign


@pytest.fixture(autouse=True)
def _ensure_fernet(monkeypatch):
    """Tests in this module need a real Fernet key to round-trip secrets.

    Generate a fresh one rather than relying on ambient env state — the
    test suite must be deterministic regardless of what FERNET_KEY the
    developer happens to have exported.
    """
    from cryptography.fernet import Fernet

    from app.config import settings

    monkeypatch.setattr(settings, "FERNET_KEY", Fernet.generate_key().decode())


class _FakeWebhook:
    """Stand-in for a ``WebhookModel`` row, just enough for ``_sign``."""

    def __init__(self, secret_encrypted: bytes | None, secret_hash: str | None, legacy_signing: bool):
        self.secret_encrypted = secret_encrypted
        self.secret_hash = secret_hash
        self.legacy_signing = legacy_signing


def test_raw_secret_signature_is_receiver_verifiable():
    """Receiver holding the raw secret can verify ``X-Webhook-Signature``.

    The signing string contract is ``f"{ts}.{body}"`` so receivers can
    cheaply prepend the header timestamp to the request body before
    reproducing the HMAC.
    """
    raw_secret = b"super-secret-key-32-bytes-long-aa"
    webhook = _FakeWebhook(
        secret_encrypted=encrypt_bytes(raw_secret),
        secret_hash=hashlib.sha256(raw_secret).hexdigest(),
        legacy_signing=False,
    )

    headers, body = _sign(webhook, "job.completed", {"job_id": "abc"})

    # Headers contract — timestamp + sha256 signature, no legacy marker.
    assert "X-Webhook-Timestamp" in headers
    assert headers["X-Webhook-Signature"].startswith("sha256=")
    assert "X-Webhook-Legacy-Signing" not in headers

    # Reproduce signature on the receiver side.
    ts = headers["X-Webhook-Timestamp"]
    signing_string = f"{ts}.".encode() + body
    expected = hmac.new(raw_secret, signing_string, hashlib.sha256).hexdigest()
    actual = headers["X-Webhook-Signature"].removeprefix("sha256=")
    assert hmac.compare_digest(expected, actual)


def test_body_is_canonical_json():
    """``body`` must be the exact bytes the dispatcher will POST.

    Receivers reproduce the HMAC over the raw bytes — any whitespace
    normalisation or key reordering between dispatch and verification
    breaks the signature.
    """
    raw_secret = b"my-secret"
    webhook = _FakeWebhook(
        secret_encrypted=encrypt_bytes(raw_secret),
        secret_hash="ignored",
        legacy_signing=False,
    )

    payload = {"job_id": "abc", "status": "completed"}
    _, body = _sign(webhook, "job.completed", payload)

    decoded = json.loads(body.decode())
    # Dispatcher wraps payloads in ``{"event": ..., "data": ...}``.
    assert decoded == {"event": "job.completed", "data": payload}


def test_no_signing_material_raises():
    """A webhook row with neither raw secret nor legacy hash is unusable.

    The dispatcher must surface a clear error rather than silently POST
    an unsigned request — that would let an attacker who can reach the
    receiver impersonate the system.
    """
    webhook = _FakeWebhook(
        secret_encrypted=None,
        secret_hash=None,
        legacy_signing=False,
    )

    with pytest.raises(ValueError, match="no signing material"):
        _sign(webhook, "job.completed", {"x": 1})
