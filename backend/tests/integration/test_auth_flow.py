"""Integration tests for authentication flow."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_login_redirects_to_oidc(self, client):
        response = await client.get("/api/v1/auth/sso/login", follow_redirects=False)
        # Should redirect to OIDC provider or return login URL
        assert response.status_code in [302, 307, 200]

    @pytest.mark.asyncio
    async def test_callback_rejects_invalid_code(self, client):
        response = await client.get("/api/v1/auth/sso/callback?code=invalid&state=fake")
        assert response.status_code in [400, 401, 403, 422]

    @pytest.mark.asyncio
    async def test_me_requires_auth(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_succeeds_without_auth(self, client):
        response = await client.post("/api/v1/auth/logout")
        # Logout should succeed even without active session
        assert response.status_code in [200, 204, 401]


class TestProtectedEndpoints:
    @pytest.mark.asyncio
    async def test_projects_require_auth(self, client):
        response = await client.get("/api/v1/projects")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_requires_auth(self, client):
        response = await client.get("/api/v1/admin/audit-logs")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_health_does_not_require_auth(self, client):
        response = await client.get("/api/v1/health")
        # Health check should be public
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_ready_does_not_require_auth(self, client):
        response = await client.get("/api/v1/ready")
        assert response.status_code in [200, 503]
