"""Integration tests: the dev-mode auth bypass is gated on ``ENVIRONMENT``.

``get_current_user`` short-circuits to a fake admin user when no bearer
token is present **and** ``settings.ENVIRONMENT == "development"``. That
behaviour is convenient for local dev but must not leak into staging /
production where any unauthenticated request would silently get admin.

These tests prove:

* In ``production`` (the real deployment environment), an unauthenticated
  request returns 401 — the bypass is closed.
* In ``development``, the bypass remains open: an unauthenticated request
  returns a non-401 success (or a downstream 400/404, but never 401).
"""

from __future__ import annotations

import importlib

import pytest


# Use ``/auth/me`` as the canary route: it depends on ``get_current_user``
# but doesn't touch the database, so the test can isolate the bypass gate
# from unrelated DB pool / event-loop issues in the shared test runner.
_CANARY_PATH = "/api/v1/auth/me"


@pytest.mark.asyncio
async def test_production_env_rejects_unauthenticated_request(monkeypatch):
    """No bypass in production: missing token → 401."""
    # The dep reads ``settings.ENVIRONMENT`` at call time, so flipping the
    # attribute is enough — we don't need to reimport the module.
    from app.config import settings
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(_CANARY_PATH)

    assert response.status_code == 401
    payload = response.json()
    # The global exception handler flattens FastAPI's ``HTTPException(detail=...)``
    # to ``{"error": ..., "detail": ..., "request_id": ...}``.
    assert payload["error"] == "missing_token"


@pytest.mark.asyncio
async def test_development_env_allows_dev_bypass(monkeypatch):
    """Dev mode keeps the bypass open so local work doesn't need a real SSO token.

    Hits ``/auth/me`` because it doesn't touch the database — the only
    thing standing between the request and a 200 is ``get_current_user``,
    so the response cleanly reflects whether the bypass fired.
    """
    from app.config import settings
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(_CANARY_PATH)

    # Bypass fires → dev user returned with role=admin.
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "admin"
    assert body["email"] == "dev@ameritas.com"
