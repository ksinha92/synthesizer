"""Integration tests for the local password login endpoints.

These exercise the API surface only — the underlying user repo is patched so
the test doesn't depend on a live Postgres + Alembic migration. The goal is to
prove that login + change-password + sso/providers respond with the right
status codes for the documented error/branching paths.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestSsoProvidersEndpoint:
    @pytest.mark.asyncio
    async def test_providers_endpoint_returns_list(self, client):
        # Endpoint is public — no auth header needed.
        response = await client.get("/api/v1/auth/sso/providers")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body.get("providers"), list)


class TestLoginEndpoint:
    @pytest.mark.asyncio
    async def test_login_rejects_empty_body(self, client):
        # Empty payload — Pydantic should 422.
        response = await client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_blank_credentials_are_rejected(self, client):
        # Blank email/password get the same generic 401 a bogus credential
        # would — verifies the short-circuit branch before any DB lookup.
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "", "password": ""},
        )
        assert response.status_code == 401
        body = response.json()
        # App-level exception handler flattens the HTTPException detail dict.
        assert body.get("error") == "invalid_credentials"


class TestChangePasswordEndpoint:
    @pytest.mark.asyncio
    async def test_change_password_requires_auth(self, client):
        # No cookie / no header → 401 from get_current_user.
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "x", "new_password": "Strong@12345"},
        )
        assert response.status_code == 401
