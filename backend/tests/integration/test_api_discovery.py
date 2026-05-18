"""Integration tests for Discovery API endpoints."""

import pytest


class TestDiscoveryAPI:
    @pytest.mark.asyncio
    async def test_discovery_requires_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/discovery/run",
                json={"connection_id": "00000000-0000-0000-0000-000000000002"},
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pii_endpoint_requires_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/discovery/pii?schema_id=00000000-0000-0000-0000-000000000003"
            )
            assert response.status_code == 401
