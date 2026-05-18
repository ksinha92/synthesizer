"""Regression tests for the 5 issues Codex flagged at v0.9 stop-time review.

These cover real functional bugs that landed in v0.9 implementation work
across Phases 57-61 and were caught by an end-of-milestone Codex review.
Keeping them in a single file makes intent explicit: each test is named
after a Codex finding and pins the fix in place.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.shared.job import JobType


# ---------------------------------------------------------------------------
# P1 — Job type strings must match the JobType enum
# ---------------------------------------------------------------------------


def test_file_set_job_type_string_matches_enum():
    """Codex P1: synthetic_file_schemas wrote ``file_set_generation`` but the
    enum value is ``file_set``. Hydration in JobRepository._to_entity would
    raise ValueError on every read of these rows.
    """
    src = (
        "/Users/koushiksinha12/Desktop/ameritas-datawrnager/"
        "backend/app/api/v1/synthetic_file_schemas.py"
    )
    with open(src, "r") as fh:
        text = fh.read()

    # The bad string must no longer appear.
    assert 'job_type="file_set_generation"' not in text
    # The correct enum-backed value must.
    assert 'job_type="file_set"' in text
    # And it must round-trip the enum.
    assert JobType("file_set") is JobType.FILE_SET


def test_ephemeral_job_type_string_matches_enum():
    """Codex P1: ephemeral provisioning wrote ``ephemeral_provision`` but the
    enum value is ``ephemeral``.
    """
    src = (
        "/Users/koushiksinha12/Desktop/ameritas-datawrnager/"
        "backend/app/api/v1/ephemeral.py"
    )
    with open(src, "r") as fh:
        text = fh.read()

    assert 'job_type="ephemeral_provision"' not in text
    assert 'job_type="ephemeral"' in text
    assert JobType("ephemeral") is JobType.EPHEMERAL


# ---------------------------------------------------------------------------
# P2 — Clone preserves encrypted webhook material
# ---------------------------------------------------------------------------


def test_clone_project_preserves_webhook_secret_encrypted():
    """Codex P2: project clone only copied ``secret_hash``; if the source
    used the post-F14 raw-secret HMAC path, the clone fell back to legacy
    signing and HMAC verification broke silently. The clone must thread
    both ``secret_encrypted`` and ``legacy_signing`` through.
    """
    src = (
        "/Users/koushiksinha12/Desktop/ameritas-datawrnager/"
        "backend/app/api/v1/projects.py"
    )
    with open(src, "r") as fh:
        text = fh.read()

    # Look at the webhook-clone block specifically.
    clone_block_start = text.find("# Webhooks.")
    assert clone_block_start > 0, "webhook clone block missing"
    clone_block = text[clone_block_start : clone_block_start + 1200]

    assert "secret_encrypted=hook.secret_encrypted" in clone_block, (
        "clone must thread secret_encrypted"
    )
    assert "legacy_signing=hook.legacy_signing" in clone_block, (
        "clone must thread legacy_signing"
    )


# ---------------------------------------------------------------------------
# P2 — Webhook retry reuses the original delivery row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_dispatch_reuses_existing_delivery_id():
    """Codex P2: admin retry endpoint reset a delivery row to ``pending``,
    but ``dispatch()`` → ``_open_delivery_row()`` always inserted a new row.
    The reset row stayed pending forever and a later sweep would re-pick it.
    Fix: ``dispatch(existing_delivery_id=...)`` threads the row through so
    the same row captures the final outcome.
    """
    import asyncio

    from app.infrastructure.webhooks.dispatcher import WebhookDispatcher

    existing_id = uuid.uuid4()
    dispatcher = WebhookDispatcher()

    # Capture what _deliver receives. ``dispatch()`` fires ``_deliver`` via
    # ``asyncio.create_task``, so we have to let the loop drain before asserting.
    captured: dict = {}
    done = asyncio.Event()

    async def fake_deliver(webhook, event_type, payload, existing_delivery_id=None):
        captured["existing_delivery_id"] = existing_delivery_id
        captured["webhook_id"] = webhook.get("id")
        done.set()

    with patch.object(dispatcher, "_deliver", side_effect=fake_deliver):
        await dispatcher.dispatch(
            [
                {
                    "id": str(uuid.uuid4()),
                    "url": "https://example.test/hook",
                    "events": ["job.completed"],
                    "is_active": True,
                    "secret_hash": "fake",
                    "secret_encrypted": None,
                    "legacy_signing": True,
                }
            ],
            "job.completed",
            {"x": 1},
            existing_delivery_id=existing_id,
        )
        # Yield so the create_task'd coroutine actually runs.
        await asyncio.wait_for(done.wait(), timeout=1.0)

    assert captured["existing_delivery_id"] == existing_id


@pytest.mark.asyncio
async def test_webhook_deliver_skips_open_delivery_row_when_id_provided():
    """When dispatch passes through ``existing_delivery_id``, ``_deliver``
    must NOT call ``_open_delivery_row`` (otherwise we'd insert a duplicate
    row defeating the whole point of the threading).
    """
    from app.infrastructure.webhooks.dispatcher import WebhookDispatcher

    dispatcher = WebhookDispatcher()
    existing_id = uuid.uuid4()

    with patch.object(
        dispatcher, "_open_delivery_row", new_callable=AsyncMock
    ) as mock_open, patch(
        "app.infrastructure.webhooks.dispatcher.httpx.AsyncClient"
    ) as mock_client_cls:
        # httpx returns 200 immediately — terminal-success path.
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with patch.object(
            dispatcher, "_mark_delivery_sent", new_callable=AsyncMock
        ) as mock_sent:
            await dispatcher._deliver(
                {
                    "id": str(uuid.uuid4()),
                    "url": "https://example.test/hook",
                    "events": ["x"],
                    "secret_hash": "k",
                    "secret_encrypted": None,
                    "legacy_signing": True,
                    "is_active": True,
                },
                "x",
                {"y": 1},
                existing_delivery_id=existing_id,
            )

            # Did NOT open a new row.
            mock_open.assert_not_called()
            # Marked the *existing* row sent.
            mock_sent.assert_awaited_once()
            kwargs = mock_sent.await_args.kwargs
            assert kwargs["delivery_id"] == existing_id


# ---------------------------------------------------------------------------
# P2 — Ephemeral provisioning commits before .delay()
# ---------------------------------------------------------------------------


def test_ephemeral_provision_commits_before_dispatch():
    """Codex P2: ``run_ephemeral_provision_task.delay(...)`` was fired after
    only ``session.flush()``, before the request-scoped session committed.
    On a fast broker, the worker could read empty tables and 404. Fix is an
    explicit ``await session.commit()`` before ``.delay()``.

    We pin the fix by reading the source and asserting commit precedes delay.
    """
    src = (
        "/Users/koushiksinha12/Desktop/ameritas-datawrnager/"
        "backend/app/api/v1/ephemeral.py"
    )
    with open(src, "r") as fh:
        text = fh.read()

    commit_idx = text.find("await session.commit()")
    delay_idx = text.find("run_ephemeral_provision_task.delay(")
    assert commit_idx > 0, "ephemeral.py must commit before dispatch"
    assert delay_idx > 0, "ephemeral.py must call .delay() to enqueue"
    assert commit_idx < delay_idx, (
        f"commit (idx {commit_idx}) must precede .delay() (idx {delay_idx}) — "
        f"otherwise the worker can race the API session."
    )


# ---------------------------------------------------------------------------
# Second-pass Codex review findings (post-fix-batch-1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_waits_for_deliveries_when_requested():
    """Codex P1: webhook ``dispatch()`` returned immediately after scheduling
    ``_deliver`` tasks. The new Celery signal path runs under ``asyncio.run``,
    which tears the loop down when dispatch returns — cancelling every
    pending delivery before it POSTs or persists. Fix: a
    ``wait_for_completion=True`` flag for Celery callers gathers all
    delivery tasks before returning.
    """
    import asyncio

    from app.infrastructure.webhooks.dispatcher import WebhookDispatcher

    dispatcher = WebhookDispatcher()
    completion_order: list[str] = []

    async def slow_deliver(webhook, event_type, payload, existing_delivery_id=None):
        await asyncio.sleep(0.05)  # simulate the POST
        completion_order.append("delivered")

    with patch.object(dispatcher, "_deliver", side_effect=slow_deliver):
        await dispatcher.dispatch(
            [
                {
                    "id": str(uuid.uuid4()),
                    "url": "https://example.test/hook",
                    "events": ["job.completed"],
                    "is_active": True,
                    "secret_hash": "fake",
                    "secret_encrypted": None,
                    "legacy_signing": True,
                }
            ],
            "job.completed",
            {"x": 1},
            wait_for_completion=True,
        )
        completion_order.append("dispatch_returned")

    # With wait_for_completion=True, dispatch must NOT return until all
    # deliveries actually finished. Order proves it.
    assert completion_order == ["delivered", "dispatch_returned"], (
        f"dispatch returned before deliveries completed: {completion_order}"
    )


@pytest.mark.asyncio
async def test_dispatch_default_is_fire_and_forget():
    """Backward-compat: without ``wait_for_completion``, dispatch must return
    immediately so FastAPI HTTP responses aren't blocked for the full 80 s
    retry window.
    """
    import asyncio

    from app.infrastructure.webhooks.dispatcher import WebhookDispatcher

    dispatcher = WebhookDispatcher()
    completion_order: list[str] = []

    async def slow_deliver(webhook, event_type, payload, existing_delivery_id=None):
        await asyncio.sleep(0.1)
        completion_order.append("delivered")

    with patch.object(dispatcher, "_deliver", side_effect=slow_deliver):
        await dispatcher.dispatch(
            [
                {
                    "id": str(uuid.uuid4()),
                    "url": "https://example.test/hook",
                    "events": ["job.completed"],
                    "is_active": True,
                    "secret_hash": "fake",
                    "secret_encrypted": None,
                    "legacy_signing": True,
                }
            ],
            "job.completed",
            {"x": 1},
        )
        completion_order.append("dispatch_returned")
        # Let the task run before we assert.
        await asyncio.sleep(0.15)

    # dispatch returned BEFORE the slow delivery completed.
    assert completion_order == ["dispatch_returned", "delivered"], (
        f"dispatch held the caller without wait_for_completion: {completion_order}"
    )


@pytest.mark.asyncio
async def test_sse_emits_db_snapshot_before_redis_subscribe():
    """Codex P1: ``_progress_stream`` waited only on Redis pub/sub. Redis
    only delivers future messages, so a client that connects after the last
    progress event (especially after the job completed) only saw heartbeats
    and never the terminal status. Fix: emit a snapshot of the current
    ``JobModel`` state from DB before subscribing.
    """
    from app.api.v1 import events as events_module

    job_id = uuid.uuid4()

    # Snapshot returns a terminal state — stream should short-circuit
    # after emitting it (no Redis subscribe, no DB poll).
    async def fake_snapshot(_job_id):
        return {"status": "completed", "progress": 100, "result_summary": {"ok": True}}

    redis_called = False

    async def fake_redis_stream(_job_id):
        nonlocal redis_called
        redis_called = True
        if False:
            yield  # type: ignore[unreachable]

    with patch.object(events_module, "_current_state_snapshot", side_effect=fake_snapshot), \
         patch.object(events_module, "_redis_event_stream", side_effect=fake_redis_stream):
        events_emitted: list[str] = []
        async for ev in events_module._progress_stream(job_id):
            events_emitted.append(ev)

    # Must include the snapshot data event.
    snapshot_events = [e for e in events_emitted if '"status": "completed"' in e or '"status":"completed"' in e]
    assert snapshot_events, f"snapshot not emitted: {events_emitted!r}"
    # Must short-circuit on terminal — Redis subscriber never invoked.
    assert not redis_called, "stream subscribed to Redis even though job was already terminal"


def test_linked_column_ids_resolved_to_names_in_masking_task():
    """Codex P2: masking task hard-coded ``linked_column_names=[]`` so the
    engine treated every joint rule as having no peers and fell back to the
    row-identity seed. Fix: resolve each linked column_id through the
    ``column_lookup`` built from discovery and filter to the current table.

    Pin the fix by reading the source — the hard-coded empty list must be
    gone and a resolution helper must be in place.
    """
    src = (
        "/Users/koushiksinha12/Desktop/ameritas-datawrnager/"
        "backend/app/infrastructure/messaging/masking_tasks.py"
    )
    with open(src, "r") as fh:
        text = fh.read()

    # Locate the joint-rules block.
    joint_idx = text.find("if joint_rules:")
    assert joint_idx > 0, "joint_rules block missing"
    block = text[joint_idx : joint_idx + 2000]

    assert '"linked_column_names": []' not in block, (
        "joint rules still hard-code empty linked_column_names — feature is dark"
    )
    assert "_resolve_linked_names" in block, (
        "joint rules must call a resolution helper that consults column_lookup"
    )
    assert "column_lookup.get" in block, (
        "resolution must read from the column_lookup built from discovery"
    )


def test_kerberos_cache_path_uses_uid():
    """Codex P2: PostgreSQL Kerberos auth only probed ``/tmp/krb5cc_0`` (root).
    Non-root workers with a valid default cache at ``/tmp/krb5cc_<uid>`` were
    falsely rejected. Fix: use ``os.getuid()`` to derive the platform-default
    cache path.
    """
    src = (
        "/Users/koushiksinha12/Desktop/ameritas-datawrnager/"
        "backend/app/infrastructure/connectors/sql/postgresql.py"
    )
    with open(src, "r") as fh:
        text = fh.read()

    # The hard-coded root-only path must no longer be the sole check.
    # Fix should use os.getuid() to derive the per-uid path.
    assert "os.getuid()" in text, (
        "Kerberos path probe must derive from os.getuid(), not hard-code /tmp/krb5cc_0"
    )
    # Sanity check the rest of the env-var check still works.
    assert 'os.environ.get("KRB5CCNAME")' in text


def test_test_connection_handler_does_not_raise_to_force_retry():
    """Codex P2: the old wrapper turned every ``False`` from
    ``connector.test_connection()`` into a ``ConnectionError`` so it would
    flow through ``retry_async``'s transient-detection. Permanent failures
    (bad creds, missing DB) then incurred 80 s of backoff before surfacing.
    Fix: don't raise on False — treat it as the connector's final answer.
    """
    src = (
        "/Users/koushiksinha12/Desktop/ameritas-datawrnager/"
        "backend/app/application/connection/handlers.py"
    )
    with open(src, "r") as fh:
        text = fh.read()

    # Look for the test-connection wrapper specifically.
    wrapper_idx = text.find("async def _attempt() -> bool:")
    assert wrapper_idx > 0, "_attempt() wrapper missing"
    wrapper_block = text[wrapper_idx : wrapper_idx + 600]

    assert 'raise ConnectionError("connection refused")' not in wrapper_block, (
        "_attempt must not raise ConnectionError on False — that re-enters "
        "transient retry and stalls permanent failures for 80 s"
    )
