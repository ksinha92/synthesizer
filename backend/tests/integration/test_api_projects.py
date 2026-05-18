"""Integration tests for Project API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock


class TestProjectAPI:
    """Tests against FastAPI test client. Mocks DB for unit-style integration."""

    @pytest.mark.asyncio
    async def test_create_project_requires_auth(self):
        """Verify 401 without token."""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/projects", json={"name": "Test"})
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_projects_requires_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/projects")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/projects",
                headers={"Authorization": "Bearer invalid.token.here"},
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_health_endpoint_no_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code in (200, 503)  # 503 if DB not running
            assert "status" in response.json()


class TestProjectCreateWizardContract:
    """The Tonic-style New Project Wizard relies on ProjectCreate accepting
    an optional ``initial_connection`` payload + a ``run_discovery`` flag,
    plus ProjectResponse echoing the resulting ``connection_id`` and
    ``discovery_job_id``. These Pydantic-level guarantees are locked here so
    a future refactor can't silently break the wizard contract."""

    def test_project_create_accepts_legacy_minimal_body(self):
        from app.api.v1.projects import ProjectCreate

        body = ProjectCreate(name="legacy")
        assert body.name == "legacy"
        assert body.initial_connection is None
        assert body.run_discovery is False

    def test_project_create_with_initial_connection_parses(self):
        from app.api.v1.projects import ProjectCreate

        body = ProjectCreate(
            name="with-conn",
            initial_connection={
                "name": "primary",
                "connector_type": "postgresql",
                "host": "db.example.com",
                "port": 5432,
                "database_name": "prod",
                "username": "u",
                "password": "p",
            },
            run_discovery=True,
        )
        assert body.initial_connection is not None
        assert body.initial_connection.connector_type == "postgresql"
        assert body.initial_connection.extra_params == {}
        assert body.run_discovery is True

    def test_project_create_rejects_invalid_initial_connection(self):
        from pydantic import ValidationError
        from app.api.v1.projects import ProjectCreate

        with pytest.raises(ValidationError):
            ProjectCreate(
                name="bad",
                initial_connection={
                    # Missing required fields (connector_type, host, port,
                    # database_name). The wizard's confirm step must not be
                    # allowed to round-trip a half-built connection.
                    "name": "primary",
                },
            )

    def test_initial_connection_payload_matches_connection_create_fields(self):
        """Regression guard: the wizard's ``InitialConnectionPayload`` and
        the standalone ``ConnectionCreate`` must keep the same field set
        so the frontend can share the same fieldset component with the
        standalone Add Connection drawer."""

        from app.api.v1.projects import InitialConnectionPayload
        from app.api.v1.connections import ConnectionCreate

        wizard_fields = set(InitialConnectionPayload.model_fields)
        standalone_fields = set(ConnectionCreate.model_fields)
        assert wizard_fields == standalone_fields, (
            f"wizard-only: {wizard_fields - standalone_fields}, "
            f"standalone-only: {standalone_fields - wizard_fields}"
        )

    def test_project_response_carries_optional_wizard_ids(self):
        from app.api.v1.projects import ProjectResponse

        resp = ProjectResponse(
            id="proj-1",
            name="x",
            description=None,
            owner_id="user-1",
            settings={},
            created_at="2026-05-17T00:00:00",
            updated_at="2026-05-17T00:00:00",
        )
        # Defaults remain absent for legacy single-step creates.
        assert resp.connection_id is None
        assert resp.discovery_job_id is None
        # Setter path: wizard create populates these.
        resp.connection_id = "conn-1"
        resp.discovery_job_id = "job-1"
        assert resp.connection_id == "conn-1"
        assert resp.discovery_job_id == "job-1"

    @pytest.mark.asyncio
    async def test_wizard_payload_still_requires_auth(self):
        """The wizard reuses the existing project create route. Verify the
        auth gate didn't slip when the body shape grew."""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        payload = {
            "name": "wizard",
            "initial_connection": {
                "name": "primary",
                "connector_type": "postgresql",
                "host": "h",
                "port": 5432,
                "database_name": "d",
                "username": "u",
                "password": "p",
            },
            "run_discovery": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/projects", json=payload)
            assert response.status_code == 401
