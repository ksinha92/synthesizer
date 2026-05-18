"""Integration tests for Connection API endpoints."""

import pytest


class TestConnectionAPI:
    @pytest.mark.asyncio
    async def test_connections_require_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects/00000000-0000-0000-0000-000000000001/connections")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_connection_requires_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/connections",
                json={"name": "test", "connector_type": "postgresql", "host": "localhost", "port": 5432, "database_name": "test"},
            )
            assert response.status_code == 401
