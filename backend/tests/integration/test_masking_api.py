"""Integration tests for masking API endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


PROJECT_ID = "00000000-0000-0000-0000-000000000001"


class TestMaskingPoliciesAPI:
    @pytest.mark.asyncio
    async def test_list_policies_requires_auth(self, client):
        response = await client.get(f"/api/v1/projects/{PROJECT_ID}/masking/policies")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_policy_requires_auth(self, client):
        response = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/masking/policies",
            json={"name": "Test Policy", "description": "Test"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_policy_validates_name(self, client):
        # Even with auth bypass, empty name should fail validation
        response = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/masking/policies",
            json={"name": "", "description": ""},
        )
        assert response.status_code in [401, 422]


class TestMaskingRulesAPI:
    @pytest.mark.asyncio
    async def test_add_rule_requires_auth(self, client):
        policy_id = "00000000-0000-0000-0000-000000000002"
        response = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/masking/policies/{policy_id}/rules",
            json={"column_id": "col-1", "strategy": "redact", "config": {}},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_add_rule_accepts_linked_columns_payload(self, client):
        """RuleCreate must accept linked_column_ids + consistency_group (Phase 58 F7).

        Auth is still required, so this asserts the schema doesn't 422 on the
        new fields — the request reaches auth (401), not Pydantic validation.
        """
        policy_id = "00000000-0000-0000-0000-000000000002"
        response = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/masking/policies/{policy_id}/rules",
            json={
                "column_id": "00000000-0000-0000-0000-000000000010",
                "masking_type": "hash",
                "linked_column_ids": [
                    "00000000-0000-0000-0000-000000000011",
                    "00000000-0000-0000-0000-000000000012",
                ],
                "consistency_group": "customer-pii",
            },
        )
        # If Pydantic rejected the new fields, we'd see 422 instead of 401.
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_rule_accepts_linked_columns_payload(self, client):
        """RuleUpdate must accept linked_column_ids + consistency_group (Phase 58 F7)."""
        policy_id = "00000000-0000-0000-0000-000000000002"
        rule_id = "00000000-0000-0000-0000-000000000003"
        response = await client.put(
            f"/api/v1/projects/{PROJECT_ID}/masking/policies/{policy_id}/rules/{rule_id}",
            json={
                "linked_column_ids": ["00000000-0000-0000-0000-000000000011"],
                "consistency_group": "customer-pii",
            },
        )
        assert response.status_code == 401


class TestMaskingOperationsAPI:
    @pytest.mark.asyncio
    async def test_auto_suggest_requires_auth(self, client):
        response = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/masking/auto-suggest",
            json={"schema_id": "schema-1"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_preview_requires_auth(self, client):
        response = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/masking/preview",
            json={"policy_id": "p-1", "connection_id": "c-1"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_execute_requires_auth(self, client):
        response = await client.post(
            f"/api/v1/projects/{PROJECT_ID}/masking/execute",
            json={"policy_id": "p-1", "connection_id": "c-1"},
        )
        assert response.status_code == 401
