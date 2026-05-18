"""Integration test for the connector-metadata catalogue endpoint."""

from __future__ import annotations

import pytest


class TestConnectorMetadataAPI:
    @pytest.mark.asyncio
    async def test_metadata_requires_auth(self) -> None:
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/connections/metadata"
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_preflight_requires_auth(self) -> None:
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/projects/00000000-0000-0000-0000-000000000001/connections/preflight",
                json={"host": "localhost", "port": 1234},
            )
            assert response.status_code == 401
