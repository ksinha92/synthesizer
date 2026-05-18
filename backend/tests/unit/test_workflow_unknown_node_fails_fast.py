"""Phase 59 F11 — unknown workflow node types raise ValueError.

The previous behavior was a silent ``await logger.awarning(...)`` and
``pass``, which meant a typo (``"sythentic"``) or a removed node type
(``"quality_check"`` post-Phase-59) would let the workflow appear to
succeed without ever running the node. Now ``_execute_node`` raises
ValueError immediately so the parent workflow fails loudly.
"""

from __future__ import annotations

import uuid

import pytest

from app.infrastructure.messaging.workflow_tasks import _execute_node


@pytest.mark.asyncio
async def test_unknown_node_type_raises_value_error() -> None:
    parent_job_uuid = uuid.uuid4()
    parent_created_by = uuid.uuid4()

    with pytest.raises(ValueError) as exc_info:
        await _execute_node(
            session=None,
            node_type="bogus",
            node_config={},
            project_id=str(uuid.uuid4()),
            parent_job_uuid=parent_job_uuid,
            parent_created_by=parent_created_by,
        )

    assert "bogus" in str(exc_info.value)
    assert "Unknown workflow node type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_removed_quality_check_node_fails_fast() -> None:
    """Phase 59 F11: the dropped ``quality_check`` type must now error.

    Legacy DAGs that still mention it will surface a clear failure on
    next execute instead of silently no-op'ing through the node.
    """
    parent_job_uuid = uuid.uuid4()
    parent_created_by = uuid.uuid4()

    with pytest.raises(ValueError) as exc_info:
        await _execute_node(
            session=None,
            node_type="quality_check",
            node_config={"config_id": str(uuid.uuid4())},
            project_id=str(uuid.uuid4()),
            parent_job_uuid=parent_job_uuid,
            parent_created_by=parent_created_by,
        )

    assert "quality_check" in str(exc_info.value)


@pytest.mark.asyncio
async def test_typo_in_node_type_raises_value_error() -> None:
    parent_job_uuid = uuid.uuid4()
    parent_created_by = uuid.uuid4()

    with pytest.raises(ValueError):
        await _execute_node(
            session=None,
            node_type="sythentic",  # missing 'h' — easy typo
            node_config={"config_id": str(uuid.uuid4())},
            project_id=str(uuid.uuid4()),
            parent_job_uuid=parent_job_uuid,
            parent_created_by=parent_created_by,
        )
