"""Unit tests for Privacy Hub `apply-all` masking enqueue (Phase 57 F3)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1 import privacy_hub
from app.api.v1.privacy_hub import ApplyAllRequest, apply_all


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
POLICY_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
CONNECTION_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
COLUMN_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


def _make_session() -> MagicMock:
    """A session double that records adds and supports async flush."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_apply_all_no_connection_returns_null_job_id_and_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the project has no connection, apply-all still creates rules but
    skips the masking enqueue and surfaces `no_connection_to_mask`."""
    session = _make_session()

    monkeypatch.setattr(
        privacy_hub,
        "_project_sensitive_columns",
        AsyncMock(return_value=[(COLUMN_ID, "email")]),
    )
    monkeypatch.setattr(
        privacy_hub,
        "_project_protected_column_ids",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        privacy_hub,
        "_get_or_create_default_policy",
        AsyncMock(return_value=POLICY_ID),
    )

    # Connection repo returns empty list → no connection to mask against.
    repo_instance = MagicMock()
    repo_instance.find_by_project_id = AsyncMock(return_value=[])
    monkeypatch.setattr(
        privacy_hub,
        "SQLAlchemyConnectionRepository",
        MagicMock(return_value=repo_instance),
    )

    delay_mock = MagicMock()
    with patch(
        "app.infrastructure.messaging.masking_tasks.run_masking_task.delay",
        delay_mock,
    ):
        response = await apply_all(
            project_id=PROJECT_ID,
            body=ApplyAllRequest(pii_types=["email"]),
            current_user={"id": str(USER_ID)},
            session=session,
        )

    assert response.rules_created == 1
    assert response.policy_id == str(POLICY_ID)
    assert response.job_id is None
    assert response.note == "no_connection_to_mask"
    delay_mock.assert_not_called()
    repo_instance.find_by_project_id.assert_awaited_once_with(PROJECT_ID, limit=1)


@pytest.mark.asyncio
async def test_apply_all_with_connection_enqueues_masking_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a connection exists, apply-all enqueues `run_masking_task.delay`
    exactly once with policy_id/connection_id matching the resolved values."""
    session = _make_session()

    monkeypatch.setattr(
        privacy_hub,
        "_project_sensitive_columns",
        AsyncMock(return_value=[(COLUMN_ID, "email")]),
    )
    monkeypatch.setattr(
        privacy_hub,
        "_project_protected_column_ids",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        privacy_hub,
        "_get_or_create_default_policy",
        AsyncMock(return_value=POLICY_ID),
    )

    connection = SimpleNamespace(id=CONNECTION_ID, project_id=PROJECT_ID)
    repo_instance = MagicMock()
    repo_instance.find_by_project_id = AsyncMock(return_value=[connection])
    monkeypatch.setattr(
        privacy_hub,
        "SQLAlchemyConnectionRepository",
        MagicMock(return_value=repo_instance),
    )

    delay_mock = MagicMock()
    with patch(
        "app.infrastructure.messaging.masking_tasks.run_masking_task.delay",
        delay_mock,
    ):
        response = await apply_all(
            project_id=PROJECT_ID,
            body=ApplyAllRequest(pii_types=["email"]),
            current_user={"id": str(USER_ID)},
            session=session,
        )

    assert response.rules_created == 1
    assert response.policy_id == str(POLICY_ID)
    assert response.note is None
    assert response.job_id is not None

    # Masking task enqueued exactly once with positional args:
    # (policy_id, connection_id, project_id, job_id) — all stringified UUIDs.
    delay_mock.assert_called_once()
    args, kwargs = delay_mock.call_args
    assert kwargs == {}
    assert args[0] == str(POLICY_ID)
    assert args[1] == str(CONNECTION_ID)
    assert args[2] == str(PROJECT_ID)
    # args[3] is the JobModel.id stringified — verify it parses and matches
    # what was attached to the response.
    assert args[3] == response.job_id
    uuid.UUID(args[3])  # parses cleanly


@pytest.mark.asyncio
async def test_apply_all_preserves_idempotency_for_already_protected_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Columns that already have a rule must NOT cause a new rule to be added,
    and with no targets we must not enqueue a masking task."""
    session = _make_session()

    # Sensitive column is already protected → targets list is empty.
    monkeypatch.setattr(
        privacy_hub,
        "_project_sensitive_columns",
        AsyncMock(return_value=[(COLUMN_ID, "email")]),
    )
    monkeypatch.setattr(
        privacy_hub,
        "_project_protected_column_ids",
        AsyncMock(return_value={COLUMN_ID}),
    )
    monkeypatch.setattr(
        privacy_hub,
        "_get_or_create_default_policy",
        AsyncMock(return_value=POLICY_ID),
    )

    repo_instance = MagicMock()
    repo_instance.find_by_project_id = AsyncMock(return_value=[])
    monkeypatch.setattr(
        privacy_hub,
        "SQLAlchemyConnectionRepository",
        MagicMock(return_value=repo_instance),
    )

    delay_mock = MagicMock()
    with patch(
        "app.infrastructure.messaging.masking_tasks.run_masking_task.delay",
        delay_mock,
    ):
        response = await apply_all(
            project_id=PROJECT_ID,
            body=ApplyAllRequest(pii_types=["email"]),
            current_user={"id": str(USER_ID)},
            session=session,
        )

    assert response.rules_created == 0
    assert response.policy_id == str(POLICY_ID)
    assert response.job_id is None
    delay_mock.assert_not_called()
    # Connection repo isn't consulted when there are no rules to enqueue masking for.
    repo_instance.find_by_project_id.assert_not_called()
