"""Tests for the progress pub/sub helper (Phase 59 F13)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.infrastructure.messaging.progress_pubsub import channel_for, publish_progress


def test_channel_for_returns_namespaced_channel():
    assert channel_for("abc") == "job:abc:progress"
    # UUID-shaped ids round-trip the same way.
    assert channel_for("00000000-0000-0000-0000-000000000001") == (
        "job:00000000-0000-0000-0000-000000000001:progress"
    )


def test_publish_progress_returns_true_on_success():
    mock_client = MagicMock()
    payload = {"status": "running", "progress": 42}

    with patch("redis.from_url", return_value=mock_client) as ctor:
        result = publish_progress("job-1", payload)

    assert result is True
    ctor.assert_called_once()
    # Channel + JSON-encoded payload were passed to redis.publish.
    args, _ = mock_client.publish.call_args
    assert args[0] == "job:job-1:progress"
    assert json.loads(args[1]) == payload


def test_publish_progress_swallows_exception_and_returns_false():
    """Any Redis-side failure must NOT crash the worker — return False."""

    def _boom(*_args, **_kwargs):
        raise ConnectionError("redis unreachable")

    with patch("redis.from_url", side_effect=_boom):
        result = publish_progress("job-2", {"status": "running"})

    assert result is False
