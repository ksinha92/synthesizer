"""Unit tests for the in-process token-bucket rate limiter (Phase 60 F16).

The limiter has three observable behaviours that matter to callers:

1. First N=capacity requests within the window all succeed.
2. The N+1-th request raises ``HTTPException(429)`` with a ``Retry-After``
   header so clients can back off cleanly.
3. Once enough simulated time has elapsed, tokens refill and traffic
   resumes — verified by patching ``time.monotonic`` so the test stays
   wall-clock-free.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.infrastructure.auth import rate_limit as rate_limit_module
from app.infrastructure.auth.rate_limit import _reset_buckets, rate_limit


def _make_request(path: str):
    """Build a minimal Request-like object that the limiter reads from."""
    request = MagicMock()
    # The dependency only needs ``request.url.path``.
    request.url.path = path
    return request


@pytest.fixture(autouse=True)
def _clear_buckets():
    """Each test starts from a clean bucket store so state doesn't leak."""
    _reset_buckets()
    yield
    _reset_buckets()


@pytest.mark.asyncio
async def test_first_five_requests_succeed():
    """Bucket starts full (capacity=5) — five back-to-back hits all pass."""
    dep = rate_limit(per_min=5)
    user = {"id": "user-A"}
    request = _make_request("/api/v1/projects/p/connections/preflight")

    # Five quick hits at the same simulated instant.
    with patch.object(rate_limit_module.time, "monotonic", return_value=1000.0):
        for _ in range(5):
            assert await dep(request=request, current_user=user) is None


@pytest.mark.asyncio
async def test_sixth_request_within_window_raises_429():
    """Once tokens hit zero, the next request is throttled."""
    dep = rate_limit(per_min=5)
    user = {"id": "user-A"}
    request = _make_request("/api/v1/projects/p/connections/preflight")

    with patch.object(rate_limit_module.time, "monotonic", return_value=2000.0):
        for _ in range(5):
            await dep(request=request, current_user=user)
        with pytest.raises(HTTPException) as exc:
            await dep(request=request, current_user=user)

    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "rate_limited"
    # ``Retry-After`` is the contract clients (curl, httpx, browser) rely on.
    assert "Retry-After" in exc.value.headers
    assert int(exc.value.headers["Retry-After"]) >= 1
    assert exc.value.detail["retry_after_seconds"] >= 1


@pytest.mark.asyncio
async def test_bucket_refills_after_simulated_wait():
    """After 60 simulated seconds the bucket is full again.

    We exhaust the bucket at t=3000, then advance to t=3060 and verify a
    new request succeeds without contacting the system clock.
    """
    dep = rate_limit(per_min=5)
    user = {"id": "user-A"}
    request = _make_request("/api/v1/projects/p/connections/preflight")

    with patch.object(rate_limit_module.time, "monotonic") as mock_clock:
        mock_clock.return_value = 3000.0
        for _ in range(5):
            await dep(request=request, current_user=user)

        # Next call still at t=3000 → 429.
        with pytest.raises(HTTPException):
            await dep(request=request, current_user=user)

        # Jump forward a full minute — bucket should refill to capacity.
        mock_clock.return_value = 3060.0
        # Fresh five-pack succeeds.
        for _ in range(5):
            assert await dep(request=request, current_user=user) is None


@pytest.mark.asyncio
async def test_different_users_have_independent_buckets():
    """The key includes user id — one user hitting the cap doesn't block another."""
    dep = rate_limit(per_min=5)
    request = _make_request("/api/v1/projects/p/connections/preflight")

    with patch.object(rate_limit_module.time, "monotonic", return_value=4000.0):
        # Exhaust user A.
        user_a = {"id": "user-A"}
        for _ in range(5):
            await dep(request=request, current_user=user_a)
        with pytest.raises(HTTPException):
            await dep(request=request, current_user=user_a)

        # User B is untouched.
        user_b = {"id": "user-B"}
        assert await dep(request=request, current_user=user_b) is None


@pytest.mark.asyncio
async def test_different_endpoints_have_independent_buckets():
    """The key includes ``request.url.path`` — preflight cap doesn't bleed into other endpoints."""
    dep = rate_limit(per_min=5)
    user = {"id": "user-A"}

    preflight = _make_request("/api/v1/projects/p/connections/preflight")
    other = _make_request("/api/v1/projects/p/connections/test")

    with patch.object(rate_limit_module.time, "monotonic", return_value=5000.0):
        for _ in range(5):
            await dep(request=preflight, current_user=user)
        # Preflight bucket is empty.
        with pytest.raises(HTTPException):
            await dep(request=preflight, current_user=user)
        # Other endpoint's bucket is still full.
        assert await dep(request=other, current_user=user) is None
