"""Async retry-with-backoff helper for connector-level transient failures.

Classifies common driver exceptions as transient (network blip, warehouse
cold-start, DNS hiccup) vs permanent (auth failure, missing database). Only
transient errors are retried — permanent ones fail fast so the user sees
the real problem instead of a multiplied timeout.
"""

from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")

DEFAULT_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 0.5  # seconds
DEFAULT_MAX_DELAY = 8.0


# Substrings we treat as transient. Driver-agnostic — every Python DB driver
# eventually surfaces these phrases either in the exception type name or its
# message.
_TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "connection lost",
    "broken pipe",
    "temporary failure",
    "name resolution",
    "no route to host",
    "503",
    "could not connect",
    "warehouse is suspended",
    "warehouse is starting",
    "cluster is restarting",
)


def is_transient(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    if "timeout" in name or "connectionerror" in name or "operationalerror" in name:
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    connector: str = "unknown",
) -> T:
    """Run ``func`` with exponential backoff on transient errors.

    Final attempt re-raises the original exception. Sleeps include 25% jitter
    to avoid thundering-herd reconnect storms.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001 — driver exceptions are heterogeneous
            last_exc = exc
            if attempt == attempts or not is_transient(exc):
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay *= 1 + random.uniform(-0.25, 0.25)
            await logger.awarning(
                "connector_retry",
                connector=connector,
                attempt=attempt,
                next_delay_s=round(delay, 2),
                error=type(exc).__name__,
            )
            await asyncio.sleep(max(delay, 0.0))
    # Unreachable — loop either returns or raises.
    raise last_exc  # type: ignore[misc]
