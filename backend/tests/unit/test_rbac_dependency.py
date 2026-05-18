"""Unit tests for ``require_project_membership`` (Phase 60 F15).

The dependency is the single chokepoint protecting every project-scoped
feature router. These tests pin the behaviour:

* System admin always passes.
* Service-account callers always pass (they're not project-scoped).
* Project owner passes implicitly without an explicit ``project_members`` row.
* Explicit members pass when their stored role meets the required minimum.
* Members fall through to 403 when the role rank is too low.
* Non-members get a 403 with the right error envelope.

We exercise the dependency directly (not through the FastAPI router) so
the test stays fast and doesn't need a database — the session and ORM
models are stubbed via ``unittest.mock``.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.infrastructure.auth.rbac import require_project_membership


def _make_session(owner_id: uuid.UUID | None, member_role: str | None):
    """Build an async session double whose two ``execute`` calls return:

    1. The project owner id (or ``None`` if the project doesn't exist).
    2. The member's role string (or ``None`` if not a member).

    Matches the query order inside ``require_project_membership``.
    """
    owner_result = MagicMock()
    owner_result.scalar_one_or_none.return_value = owner_id
    member_result = MagicMock()
    member_result.scalar_one_or_none.return_value = member_role

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[owner_result, member_result])
    return session


@pytest.mark.asyncio
async def test_system_admin_bypasses_membership_check():
    """A user with ``role='admin'`` short-circuits before any DB call."""
    dep = require_project_membership("editor")
    session = MagicMock()
    session.execute = AsyncMock()

    user = {"id": str(uuid.uuid4()), "role": "admin"}
    result = await dep(
        project_id=uuid.uuid4(), current_user=user, session=session
    )

    assert result is user
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_account_bypasses_membership_check():
    """Service-account principals (worker callbacks) aren't project-scoped."""
    dep = require_project_membership("editor")
    session = MagicMock()
    session.execute = AsyncMock()

    user = {"id": None, "role": "service_account"}
    result = await dep(
        project_id=uuid.uuid4(), current_user=user, session=session
    )

    assert result is user
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_project_owner_passes_without_explicit_member_row():
    """``projects.owner_id == user.id`` grants implicit admin rights."""
    user_uuid = uuid.uuid4()
    project_id = uuid.uuid4()

    dep = require_project_membership("editor")
    # Only the owner-lookup query should run.
    owner_result = MagicMock()
    owner_result.scalar_one_or_none.return_value = user_uuid
    session = MagicMock()
    session.execute = AsyncMock(return_value=owner_result)

    user = {"id": str(user_uuid), "role": "viewer"}
    result = await dep(
        project_id=project_id, current_user=user, session=session
    )

    assert result is user
    # Should not reach the project_members lookup.
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_viewer_can_read_but_not_write():
    """A viewer-role member satisfies ``viewer`` but not ``editor``."""
    user_uuid = uuid.uuid4()
    project_id = uuid.uuid4()
    owner_id = uuid.uuid4()  # Different from user → not owner.

    read_dep = require_project_membership("viewer")
    write_dep = require_project_membership("editor")

    user = {"id": str(user_uuid), "role": "viewer"}

    read_session = _make_session(owner_id, "viewer")
    assert await read_dep(
        project_id=project_id, current_user=user, session=read_session
    ) is user

    write_session = _make_session(owner_id, "viewer")
    with pytest.raises(HTTPException) as exc:
        await write_dep(
            project_id=project_id, current_user=user, session=write_session
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "insufficient_role"
    assert exc.value.detail["have"] == "viewer"
    assert exc.value.detail["need"] == "editor"


@pytest.mark.asyncio
async def test_editor_can_read_and_write():
    """An editor member satisfies both viewer and editor minimums."""
    user_uuid = uuid.uuid4()
    project_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    user = {"id": str(user_uuid), "role": "viewer"}

    for required in ("viewer", "editor"):
        session = _make_session(owner_id, "editor")
        dep = require_project_membership(required)
        result = await dep(
            project_id=project_id, current_user=user, session=session
        )
        assert result is user


@pytest.mark.asyncio
async def test_project_admin_member_can_do_everything():
    """A member with role='admin' satisfies the highest tier."""
    user_uuid = uuid.uuid4()
    project_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    user = {"id": str(user_uuid), "role": "viewer"}

    for required in ("viewer", "editor", "admin"):
        session = _make_session(owner_id, "admin")
        dep = require_project_membership(required)
        assert await dep(
            project_id=project_id, current_user=user, session=session
        ) is user


@pytest.mark.asyncio
async def test_non_member_gets_403_with_project_id():
    """Authenticated but not a member of *this* project → 403 with the id."""
    user_uuid = uuid.uuid4()
    project_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    dep = require_project_membership("viewer")
    session = _make_session(owner_id, None)

    user = {"id": str(user_uuid), "role": "viewer"}
    with pytest.raises(HTTPException) as exc:
        await dep(
            project_id=project_id, current_user=user, session=session
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "not_a_project_member"
    assert exc.value.detail["project_id"] == str(project_id)


@pytest.mark.asyncio
async def test_missing_user_id_raises_401():
    """Defence-in-depth: if ``current_user`` has no id, refuse."""
    dep = require_project_membership("viewer")
    session = MagicMock()
    session.execute = AsyncMock()

    user = {"id": None, "role": "viewer"}
    with pytest.raises(HTTPException) as exc:
        await dep(
            project_id=uuid.uuid4(), current_user=user, session=session
        )
    assert exc.value.status_code == 401
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_user_id_raises_401():
    """A non-UUID id from the auth layer is rejected, not silently allowed."""
    dep = require_project_membership("viewer")
    session = MagicMock()
    session.execute = AsyncMock()

    user = {"id": "not-a-uuid", "role": "viewer"}
    with pytest.raises(HTTPException) as exc:
        await dep(
            project_id=uuid.uuid4(), current_user=user, session=session
        )
    assert exc.value.status_code == 401
