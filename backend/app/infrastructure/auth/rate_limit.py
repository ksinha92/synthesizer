"""In-process token-bucket rate limiter.

v0.9 single-worker assumption: state lives in the FastAPI process. If we
scale to multiple workers / pods this needs to move to Redis. For now the
preflight endpoint is the only caller, so the simple in-process bucket is
sufficient and avoids dragging Redis into the auth boundary.

Usage::

    @router.post("/preflight")
    async def preflight(..., _rl=Depends(rate_limit(per_min=5))):
        ...

The dependency raises ``HTTPException(429)`` with ``Retry-After`` header
when the bucket is empty. Buckets are keyed by ``user_id:request_path`` so
the same user can hit different endpoints independently, but multiple
calls to the same endpoint from the same user share a bucket.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable

from fastapi import Depends, HTTPException, Request

from app.infrastructure.auth.dependencies import get_current_user


class _Bucket:
    __slots__ = ("tokens", "last_refill")

    def __init__(self, capacity: float) -> None:
        self.tokens = capacity
        self.last_refill = time.monotonic()


# Exported so tests can monkey-patch / clear between cases.
_buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(5.0))
_lock = threading.Lock()


def _reset_buckets() -> None:
    """Test helper: drop all bucket state.

    Lives at module scope so test files can call
    ``app.infrastructure.auth.rate_limit._reset_buckets()`` directly without
    touching the protected globals.
    """

    with _lock:
        _buckets.clear()


def rate_limit(
    per_min: int = 5,
    key_fn: Callable[[Request], str] | None = None,
):
    """Return a FastAPI dependency that throttles requests at ``per_min`` / min.

    Args:
        per_min: Bucket capacity (also the steady-state rate per minute).
        key_fn: Optional override that derives the bucket key from the
            ``Request``. Defaults to ``"{user_id}:{request.url.path}"``.

    The dependency is async because ``get_current_user`` is async; the
    bucket arithmetic itself runs under a short-lived lock.
    """

    capacity = float(per_min)
    refill_rate = per_min / 60.0  # tokens per second

    async def dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ) -> None:
        if key_fn is not None:
            key = key_fn(request)
        else:
            user_id = current_user.get("id") or "anonymous"
            key = f"{user_id}:{request.url.path}"

        now = time.monotonic()
        with _lock:
            bucket = _buckets[key]
            elapsed = now - bucket.last_refill
            bucket.tokens = min(capacity, bucket.tokens + elapsed * refill_rate)
            bucket.last_refill = now
            if bucket.tokens < 1.0:
                # Time to wait until we have one full token. +1 so the
                # client always sees a non-zero Retry-After even when we're
                # only fractionally short.
                retry_after = int((1.0 - bucket.tokens) / refill_rate) + 1
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limited",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.tokens -= 1.0

    return dependency
