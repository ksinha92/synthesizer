"""Role-based access control middleware."""

from __future__ import annotations

import uuid
from enum import IntEnum
from typing import Literal

from fastapi import Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.persistence.database import get_session


class ProjectRole(IntEnum):
    VIEWER = 1
    EDITOR = 2
    ADMIN = 3


ROLE_MAP = {"viewer": ProjectRole.VIEWER, "editor": ProjectRole.EDITOR, "admin": ProjectRole.ADMIN}

# Numeric ranks mirror ROLE_MAP for the project-membership dependency below;
# kept as plain ints so callers don't have to import the IntEnum.
ROLE_RANK = {"viewer": 0, "editor": 1, "admin": 2}


def require_project_role(min_role: ProjectRole):
    """FastAPI dependency that enforces minimum project role."""

    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role_str = current_user.get("role", "viewer")
        user_role = ROLE_MAP.get(user_role_str, ProjectRole.VIEWER)

        if user_role < min_role:
            raise HTTPException(
                status_code=403,
                detail={"error": "insufficient_permissions", "detail": f"Requires {min_role.name.lower()} role, you have {user_role_str}"},
            )
        return current_user

    return checker


require_admin = require_project_role(ProjectRole.ADMIN)
require_editor = require_project_role(ProjectRole.EDITOR)
require_viewer = require_project_role(ProjectRole.VIEWER)


async def assert_project_access(
    project_id: uuid.UUID,
    current_user: dict,
    session: AsyncSession,
    min_role: Literal["viewer", "editor", "admin"] = "viewer",
) -> None:
    """Imperative version of :func:`require_project_membership`.

    Use inside handlers whose path does not include ``{project_id}`` (so the
    FastAPI dependency cannot bind it automatically), e.g. SSE streams,
    assistant endpoints, or any other surface that derives the project id
    from a query/body. Raises ``HTTPException(403)`` on insufficient access.

    Mirrors the same access ladder as :func:`require_project_membership`:
    system admin > service account > project owner > explicit member.
    """
    if current_user.get("role") == "admin":
        return
    if current_user.get("role") == "service_account":
        return

    user_id_raw = current_user.get("id")
    if not user_id_raw:
        raise HTTPException(
            401,
            {"error": "missing_user_id", "detail": "Authenticated user has no id"},
        )
    try:
        user_uuid = uuid.UUID(user_id_raw)
    except (TypeError, ValueError):
        raise HTTPException(
            401,
            {"error": "invalid_user_id", "detail": "Authenticated user id is not a UUID"},
        )

    from app.infrastructure.persistence.models.member import ProjectMemberModel
    from app.infrastructure.persistence.models.project import ProjectModel

    owner_row = await session.execute(
        select(ProjectModel.owner_id).where(ProjectModel.id == project_id)
    )
    owner_id = owner_row.scalar_one_or_none()
    if owner_id is not None and owner_id == user_uuid:
        return

    member_row = await session.execute(
        select(ProjectMemberModel.role).where(
            ProjectMemberModel.project_id == project_id,
            ProjectMemberModel.user_id == user_uuid,
        )
    )
    member_role = member_row.scalar_one_or_none()
    if member_role is None:
        raise HTTPException(
            403,
            {"error": "not_a_project_member", "project_id": str(project_id)},
        )

    have_rank = ROLE_RANK.get(member_role, -1)
    need_rank = ROLE_RANK[min_role]
    if have_rank < need_rank:
        raise HTTPException(
            403,
            {"error": "insufficient_role", "have": member_role, "need": min_role},
        )


def require_project_membership(
    min_role: Literal["viewer", "editor", "admin"] = "editor",
):
    """FastAPI dependency: verify ``current_user`` is a member of ``project_id``
    with at least ``min_role``.

    Access ladder (top wins):

    1. **System admin** — ``current_user.role == "admin"`` always passes.
    2. **Project owner** — the user listed on ``projects.owner_id`` always passes
       (acts as the implicit admin of their project).
    3. **Service account** — ``current_user.role == "service_account"`` passes.
       Service accounts are project-agnostic by design (used for webhook + worker
       callbacks) so we don't gate them on membership.
    4. **Explicit member** — a row in ``project_members`` with role ≥ ``min_role``.

    Otherwise raises 403.
    """

    async def _dep(
        project_id: uuid.UUID = Path(...),
        current_user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        # System admin always allowed.
        if current_user.get("role") == "admin":
            return current_user

        # Service accounts (worker callbacks, integrations) are not project-scoped.
        if current_user.get("role") == "service_account":
            return current_user

        user_id_raw = current_user.get("id")
        if not user_id_raw:
            raise HTTPException(
                401,
                {"error": "missing_user_id", "detail": "Authenticated user has no id"},
            )
        try:
            user_uuid = uuid.UUID(user_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(
                401,
                {"error": "invalid_user_id", "detail": "Authenticated user id is not a UUID"},
            )

        # Lazy imports to keep this module import-light (and tests can patch
        # the symbols on the rbac module).
        from app.infrastructure.persistence.models.member import ProjectMemberModel
        from app.infrastructure.persistence.models.project import ProjectModel

        # Project owner is always an implicit admin of their project.
        owner_row = await session.execute(
            select(ProjectModel.owner_id).where(ProjectModel.id == project_id)
        )
        owner_id = owner_row.scalar_one_or_none()
        if owner_id is not None and owner_id == user_uuid:
            return current_user

        # Look up explicit membership.
        member_row = await session.execute(
            select(ProjectMemberModel.role).where(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_uuid,
            )
        )
        member_role = member_row.scalar_one_or_none()
        if member_role is None:
            raise HTTPException(
                403,
                {
                    "error": "not_a_project_member",
                    "project_id": str(project_id),
                },
            )

        have_rank = ROLE_RANK.get(member_role, -1)
        need_rank = ROLE_RANK[min_role]
        if have_rank < need_rank:
            raise HTTPException(
                403,
                {
                    "error": "insufficient_role",
                    "have": member_role,
                    "need": min_role,
                },
            )

        return current_user

    return _dep
