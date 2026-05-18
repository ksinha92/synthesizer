"""Unit tests for GenerateReportHandler.

Phase 57 F1 verifies the handler now drives all three repositories
(connection, discovery, masking) instead of shipping empty lists into the
reporters. Regressing to the old empty-payload behavior would re-introduce
the bug that made every HIPAA/GDPR/CCPA PDF useless.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.compliance.commands import GenerateReportCommand
from app.application.compliance.handlers import GenerateReportHandler
from app.domain.compliance.entities import ComplianceReport
from app.domain.connection.entities import Connection
from app.domain.connection.value_objects import (
    ConnectionCredentials,
    ConnectionStatus,
    ConnectorType,
)
from app.domain.discovery.entities import (
    DiscoveredColumn,
    DiscoveredSchema,
    DiscoveredTable,
)
from app.domain.discovery.value_objects import Classification, PIIConfidence, PIIType
from app.domain.masking.entities import MaskingPolicy, MaskingRule
from app.domain.masking.value_objects import MaskingStrategy


def _make_connection(project_id, name="primary"):
    return Connection(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        connector_type=ConnectorType.POSTGRESQL,
        host="db",
        port=5432,
        database_name="app",
        credentials=ConnectionCredentials(username="u", password="p"),
        status=ConnectionStatus.UNTESTED,
    )


def _make_schema(connection_id, schema_name="public"):
    return DiscoveredSchema(
        id=uuid.uuid4(),
        connection_id=connection_id,
        schema_name=schema_name,
    )


def _make_table(schema_id, table_name="users"):
    return DiscoveredTable(
        id=uuid.uuid4(),
        schema_id=schema_id,
        table_name=table_name,
        row_count=100,
    )


def _make_pii_column(table_id, column_name="email", pii_type=PIIType.EMAIL, score=0.95):
    return DiscoveredColumn(
        id=uuid.uuid4(),
        table_id=table_id,
        column_name=column_name,
        data_type="varchar",
        pii_type=pii_type,
        pii_confidence=PIIConfidence(score=score, detector="regex"),
        classification=Classification.AUTO_CLASSIFIED,
    )


def _make_policy(project_id, name="default"):
    return MaskingPolicy(id=uuid.uuid4(), project_id=project_id, name=name, is_default=True)


def _make_rule(policy_id, column_id=None, strategy=MaskingStrategy.HASH):
    return MaskingRule(
        id=uuid.uuid4(),
        policy_id=policy_id,
        column_id=column_id or uuid.uuid4(),
        masking_type=strategy,
    )


@pytest.mark.asyncio
async def test_handle_calls_all_three_repos_and_populates_payload(monkeypatch):
    """All three repos drive the report payload; reporters get real data."""
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Fixtures
    conn = _make_connection(project_id, name="warehouse")
    schema = _make_schema(conn.id, schema_name="hr")
    table = _make_table(schema.id, table_name="employees")
    col = _make_pii_column(table.id, column_name="ssn", pii_type=PIIType.SSN, score=0.99)

    policy = _make_policy(project_id, name="hr-default")
    rule = _make_rule(policy.id, column_id=col.id, strategy=MaskingStrategy.HASH)

    # Mock repos. All async methods → AsyncMock.
    connection_repo = MagicMock()
    connection_repo.find_by_project_id = AsyncMock(return_value=[conn])

    discovery_repo = MagicMock()
    discovery_repo.find_by_connection_id = AsyncMock(return_value=[schema])
    discovery_repo.get_tables_by_schema_id = AsyncMock(return_value=[table])
    discovery_repo.get_pii_columns = AsyncMock(return_value=[col])

    masking_repo = MagicMock()
    masking_repo.find_by_project_id = AsyncMock(return_value=[policy])
    masking_repo.get_rules_by_policy = AsyncMock(return_value=[rule])

    compliance_repo = MagicMock()
    saved_holder = {}

    async def _save(entity):
        saved_holder["entity"] = entity
        return entity

    compliance_repo.save = AsyncMock(side_effect=_save)

    storage = MagicMock()
    storage.save = AsyncMock(return_value=None)

    # Avoid hitting real PDF rendering — exercises the data-flow plumbing
    # under test without dragging reportlab in.
    monkeypatch.setattr(
        "app.application.compliance.handlers.generate_pdf",
        lambda data, regulation: b"%PDF-1.4\nfake",
    )

    handler = GenerateReportHandler(
        compliance_repo=compliance_repo,
        discovery_repo=discovery_repo,
        masking_repo=masking_repo,
        storage=storage,
        connection_repo=connection_repo,
    )
    cmd = GenerateReportCommand(project_id=project_id, regulation="hipaa", user_id=user_id)

    result = await handler.handle(cmd)

    # Repos were actually invoked.
    connection_repo.find_by_project_id.assert_awaited_once_with(project_id)
    discovery_repo.find_by_connection_id.assert_awaited_once_with(conn.id)
    discovery_repo.get_tables_by_schema_id.assert_awaited_once_with(schema.id)
    discovery_repo.get_pii_columns.assert_awaited_once_with(schema.id)
    masking_repo.find_by_project_id.assert_awaited_once_with(project_id)
    masking_repo.get_rules_by_policy.assert_awaited_once_with(policy.id)

    # Storage got both the JSON and the PDF.
    assert storage.save.await_count == 2

    # Saved entity carries the regulation + a non-empty summary.
    saved = saved_holder["entity"]
    assert isinstance(saved, ComplianceReport)
    assert saved.report_type == "hipaa"
    assert saved.legacy is False
    assert saved.summary, "summary should be populated when PII rows exist"
    assert saved.summary.get("total_pii_columns") == 1
    assert result.report_type == "hipaa"


@pytest.mark.asyncio
async def test_handle_returns_empty_findings_when_repos_have_no_state(monkeypatch):
    """Edge case: project with no connections still produces a valid report.

    Regression guard — the old handler also produced empty findings, but for
    the wrong reason (hard-coded lists). The new path must keep working when
    there genuinely is nothing to report.
    """
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    connection_repo = MagicMock()
    connection_repo.find_by_project_id = AsyncMock(return_value=[])

    discovery_repo = MagicMock()
    discovery_repo.find_by_connection_id = AsyncMock(return_value=[])
    discovery_repo.get_tables_by_schema_id = AsyncMock(return_value=[])
    discovery_repo.get_pii_columns = AsyncMock(return_value=[])

    masking_repo = MagicMock()
    masking_repo.find_by_project_id = AsyncMock(return_value=[])
    masking_repo.get_rules_by_policy = AsyncMock(return_value=[])

    compliance_repo = MagicMock()
    compliance_repo.save = AsyncMock(side_effect=lambda e: e)

    storage = MagicMock()
    storage.save = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "app.application.compliance.handlers.generate_pdf",
        lambda data, regulation: b"%PDF-1.4\nfake",
    )

    handler = GenerateReportHandler(
        compliance_repo=compliance_repo,
        discovery_repo=discovery_repo,
        masking_repo=masking_repo,
        storage=storage,
        connection_repo=connection_repo,
    )

    result = await handler.handle(
        GenerateReportCommand(project_id=project_id, regulation="gdpr", user_id=user_id)
    )

    connection_repo.find_by_project_id.assert_awaited_once_with(project_id)
    # No connections → discovery_repo's per-connection methods never fire.
    discovery_repo.find_by_connection_id.assert_not_awaited()
    masking_repo.find_by_project_id.assert_awaited_once_with(project_id)
    assert result.report_type == "gdpr"


@pytest.mark.asyncio
async def test_handle_rejects_unknown_regulation():
    """Unknown regulations short-circuit before any repo work happens."""
    handler = GenerateReportHandler(
        compliance_repo=MagicMock(),
        discovery_repo=MagicMock(),
        masking_repo=MagicMock(),
        storage=MagicMock(),
        connection_repo=MagicMock(),
    )
    with pytest.raises(ValueError, match="Unknown regulation"):
        await handler.handle(
            GenerateReportCommand(
                project_id=uuid.uuid4(),
                regulation="pci",  # not supported
                user_id=uuid.uuid4(),
            )
        )
