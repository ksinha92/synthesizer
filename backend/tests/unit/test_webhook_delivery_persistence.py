"""Unit tests — failed webhook deliveries persist for replay (Phase 60 F14).

The dispatcher now writes a ``WebhookDeliveryModel`` row before the
first POST and updates it as attempts complete. We exercise the failure
path by mocking ``httpx.AsyncClient`` so every POST raises, then verify
the persistence calls fire (open as ``pending``, finalize as
``failed`` with an error message).

We don't spin up a real database — async_session_factory is patched out
the same way the DLQ-signal tests do it. The point is to assert the
dispatcher *calls* persistence at the right transitions; full ORM
round-trip is covered by the integration suite.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.infrastructure.webhooks.dispatcher import WebhookDispatcher


@pytest.fixture(autouse=True)
def _fernet_key():
    """Ensure FERNET_KEY is set so the raw-secret signing path works."""
    settings.FERNET_KEY = Fernet.generate_key().decode()


def _make_webhook_dict(secret_encrypted: bytes) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "url": "https://example.invalid/hook",
        "events": ["job.completed"],
        "secret_hash": "ignored-for-raw-path",
        "secret_encrypted": secret_encrypted,
        "legacy_signing": False,
        "is_active": True,
    }


@pytest.fixture
def _no_sleep(monkeypatch):
    """Skip the inter-attempt backoff so the test runs in <1s.

    Without this we'd sit through 5+15+60 seconds of ``asyncio.sleep``
    for the three RETRY_DELAYS values. Functionality is unaffected — we
    care that all attempts ran, not how long they waited.
    """
    async def _instant_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)


def _patch_session_factory(commit_log: list[str]):
    """Patch the async session factory so we capture lifecycle without a DB.

    The dispatcher calls ``session.add`` (open), ``session.execute`` (mark
    sent/failed), and ``session.commit`` on each path. We log which
    finalisation it ran so the test can assert it was ``failed`` rather
    than ``sent``.
    """
    session = AsyncMock()

    # `session.add` is sync in real SQLAlchemy — keep it that way so an
    # accidental `await session.add(...)` would surface as a test failure.
    session.add = MagicMock()

    def _execute(stmt):
        try:
            compiled = stmt.compile()
            params = compiled.params if hasattr(compiled, "params") else {}
            status = params.get("status")
            if status:
                commit_log.append(f"status={status}")
        except Exception:
            pass
        return MagicMock()

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()

    factory_cm = MagicMock()
    factory_cm.__aenter__ = AsyncMock(return_value=session)
    factory_cm.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=factory_cm)
    return factory, session


async def _drive(dispatcher: WebhookDispatcher, webhook: dict):
    """Run ``_deliver`` to completion (3 retries + terminal pass)."""
    await dispatcher._deliver(webhook, "job.completed", {"job_id": "abc"})


def test_failed_delivery_marks_row_failed(_no_sleep):
    """When every POST raises, the delivery row finalises as ``failed``.

    Asserts:

    * Persistence opens the row (``session.add``).
    * The dispatcher marks ``status='failed'`` on the final ``execute``.
    * ``last_error`` is populated (we set a recognisable error message).
    """
    from app.infrastructure.security.encryption import encrypt_bytes

    webhook = _make_webhook_dict(secret_encrypted=encrypt_bytes(b"raw-secret"))
    commit_log: list[str] = []
    factory, session = _patch_session_factory(commit_log)

    # Every POST raises a transport error so we exhaust retries.
    bad_client = AsyncMock()
    bad_client.post = AsyncMock(side_effect=httpx.ConnectError("destination unreachable"))

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=bad_client)
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.infrastructure.persistence.database.async_session_factory",
            factory,
        ),
        patch("httpx.AsyncClient", return_value=client_cm),
    ):
        asyncio.run(_drive(WebhookDispatcher(), webhook))

    # The dispatcher opened a row, then ran an UPDATE setting status='failed'.
    assert session.add.called, "dispatcher must persist a delivery row before POSTing"
    assert "status=failed" in commit_log, (
        f"expected dispatcher to finalise delivery as 'failed' but log was {commit_log!r}"
    )

    # Inspect the second-to-last execute call (the failure UPDATE) to
    # confirm ``last_error`` was passed through.
    failure_call = None
    for call in session.execute.call_args_list:
        stmt = call.args[0] if call.args else call.kwargs.get("statement")
        try:
            params = stmt.compile().params
        except Exception:
            continue
        if params.get("status") == "failed":
            failure_call = params
            break
    assert failure_call is not None, "no failure UPDATE captured"
    assert failure_call.get("last_error") is not None
    assert "destination unreachable" in failure_call["last_error"]


def test_successful_delivery_marks_row_sent(_no_sleep):
    """A 2xx response on first attempt finalises the row as ``sent``."""
    from app.infrastructure.security.encryption import encrypt_bytes

    webhook = _make_webhook_dict(secret_encrypted=encrypt_bytes(b"raw-secret"))
    commit_log: list[str] = []
    factory, session = _patch_session_factory(commit_log)

    good_response = MagicMock()
    good_response.status_code = 200
    good_response.raise_for_status = MagicMock()

    good_client = AsyncMock()
    good_client.post = AsyncMock(return_value=good_response)

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=good_client)
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.infrastructure.persistence.database.async_session_factory",
            factory,
        ),
        patch("httpx.AsyncClient", return_value=client_cm),
    ):
        asyncio.run(_drive(WebhookDispatcher(), webhook))

    assert "status=sent" in commit_log
    assert "status=failed" not in commit_log
