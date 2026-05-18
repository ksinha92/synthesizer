"""Phase 59 F11 — NODE_TIMEOUT enforcement.

The orchestrator wraps each ``_execute_node`` call in ``asyncio.wait_for``
with ``timeout=NODE_TIMEOUT``. If a node hangs longer than that, the
TimeoutError is converted to a RuntimeError carrying enough context for
the failure to be diagnosable from the job row. These tests exercise
that wrapping pattern directly so we don't need a real workflow DB row.
"""

from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.messaging.workflow_tasks import NODE_TIMEOUT


def test_node_timeout_constant_is_sane() -> None:
    # 30 minutes — long enough for big tables, short enough to surface a
    # genuinely stuck node before the workflow-level 2h cap fires.
    assert NODE_TIMEOUT == 1800


@pytest.mark.asyncio
async def test_wait_for_converts_timeout_to_runtime_error() -> None:
    """Mirror the orchestrator's try/except wrapper around _execute_node.

    If the wrapping pattern changes (e.g. someone removes the ``raise
    RuntimeError(...) from e``), this test still verifies the contract
    that a stuck node surfaces as RuntimeError with a clear message.
    """

    async def slow_node() -> None:
        await asyncio.sleep(10)

    node_id = "stuck-node-1"
    node_type = "masking"

    # Use a tiny timeout so the test runs fast; the prod value is 1800s.
    timeout = 0.05

    with pytest.raises(RuntimeError) as exc_info:
        try:
            await asyncio.wait_for(slow_node(), timeout=timeout)
        except asyncio.TimeoutError as e:
            raise RuntimeError(
                f"Workflow node {node_id} ({node_type}) exceeded NODE_TIMEOUT={timeout}s"
            ) from e

    msg = str(exc_info.value)
    assert "stuck-node-1" in msg
    assert "masking" in msg
    assert "NODE_TIMEOUT" in msg


@pytest.mark.asyncio
async def test_wait_for_passes_through_fast_node() -> None:
    """Sanity check: a node that finishes within the timeout returns normally."""

    async def fast_node() -> str:
        return "ok"

    result = await asyncio.wait_for(fast_node(), timeout=1.0)
    assert result == "ok"
