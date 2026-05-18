"""Integration tests for the Ephemeral Environments API (T3.1).

Lightweight contract tests — they lock the Pydantic shape and the route
wiring so refactors can't silently break the frontend. The full
provisioning controller is a follow-on and tested separately when it
lands."""

import pytest


class TestEphemeralAPIAuth:
    @pytest.mark.asyncio
    async def test_list_requires_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            project_id = "00000000-0000-0000-0000-000000000000"
            response = await client.get(f"/api/v1/projects/{project_id}/ephemeral")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_requires_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            project_id = "00000000-0000-0000-0000-000000000000"
            response = await client.post(
                f"/api/v1/projects/{project_id}/ephemeral",
                json={"name": "test", "ttl_days": 7},
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_revoke_requires_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            project_id = "00000000-0000-0000-0000-000000000000"
            env_id = "00000000-0000-0000-0000-000000000001"
            response = await client.delete(
                f"/api/v1/projects/{project_id}/ephemeral/{env_id}"
            )
            assert response.status_code == 401


class TestEphemeralCreateContract:
    """Lock the request/response shape so the Provision dialog stays in sync."""

    def test_ttl_days_has_sane_bounds(self):
        from app.api.v1.ephemeral import EphemeralCreate
        from pydantic import ValidationError

        # Below 1 is rejected
        with pytest.raises(ValidationError):
            EphemeralCreate(name="x", ttl_days=0)

        # Above 30 is rejected — caps blast radius on a forgotten env
        with pytest.raises(ValidationError):
            EphemeralCreate(name="x", ttl_days=31)

        # Boundaries accepted
        EphemeralCreate(name="x", ttl_days=1)
        EphemeralCreate(name="x", ttl_days=30)

    def test_name_is_required(self):
        from app.api.v1.ephemeral import EphemeralCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EphemeralCreate(name="", ttl_days=7)

    def test_destination_and_source_default_to_none(self):
        from app.api.v1.ephemeral import EphemeralCreate

        body = EphemeralCreate(name="qa-fixture", ttl_days=7)
        assert body.destination_connection_id is None
        assert body.source_job_id is None
        assert body.schema_name is None

    def test_response_carries_lifecycle_fields(self):
        from app.api.v1.ephemeral import EphemeralResponse

        # Field-level contract the frontend relies on.
        required_fields = {
            "id",
            "project_id",
            "name",
            "source_job_id",
            "destination_connection_id",
            "schema_name",
            "status",
            "expires_at",
            "created_by",
            "created_at",
            "updated_at",
            "seconds_remaining",
        }
        assert required_fields.issubset(set(EphemeralResponse.model_fields.keys()))
