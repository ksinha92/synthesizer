"""Unit tests — ``X-Webhook-Timestamp`` is fresh at dispatch (Phase 60 F14).

Receivers apply a ±5-min skew window to reject replays. We can't assert
the rejection logic from the dispatcher side (that lives at the
receiver, by design), but we *can* assert that the timestamp we emit is
fresh — within a couple of seconds of ``time.time()`` at dispatch — so
receivers don't false-reject our own deliveries.

This is a regression-watcher: a future refactor that, say, accidentally
re-uses an old timestamp from a captured signing material struct, would
trip this test immediately.
"""

from __future__ import annotations

import time

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.infrastructure.security.encryption import encrypt_bytes
from app.infrastructure.webhooks.dispatcher import _sign


@pytest.fixture(autouse=True)
def _fernet_key():
    settings.FERNET_KEY = Fernet.generate_key().decode()


class _FakeWebhook:
    def __init__(self):
        self.secret_encrypted = encrypt_bytes(b"raw-secret")
        self.secret_hash = "ignored"
        self.legacy_signing = False


def test_timestamp_is_within_two_seconds_of_now():
    """``X-Webhook-Timestamp`` must equal "now" at dispatch (±2s).

    Two-second tolerance accommodates slow CI workers without papering
    over an actual stale-timestamp regression.
    """
    before = int(time.time())
    headers, _body = _sign(_FakeWebhook(), "job.completed", {"x": 1})
    after = int(time.time())

    ts = int(headers["X-Webhook-Timestamp"])
    assert before - 2 <= ts <= after + 2, (
        f"timestamp {ts} not within [{before - 2}, {after + 2}]"
    )


def test_timestamp_present_for_legacy_path_too():
    """Even the legacy signing path emits ``X-Webhook-Timestamp``.

    The header is harmless on the legacy path (not part of the
    signature) but lets monitoring detect skew on every delivery
    uniformly.
    """
    import hashlib

    webhook = _FakeWebhook()
    webhook.secret_encrypted = None
    webhook.secret_hash = hashlib.sha256(b"x").hexdigest()
    webhook.legacy_signing = True

    headers, _body = _sign(webhook, "job.completed", {"x": 1})
    assert "X-Webhook-Timestamp" in headers


def test_timestamp_is_an_integer_string():
    """Receivers parse the header as ``int(ts)`` — emit canonical form.

    A float-formatted timestamp ("1700000000.123") would silently break
    naive ``int(header)`` parsers downstream.
    """
    headers, _body = _sign(_FakeWebhook(), "job.completed", {"x": 1})
    raw = headers["X-Webhook-Timestamp"]
    assert raw.isdigit(), f"timestamp header should be a unix-second integer string, got {raw!r}"
