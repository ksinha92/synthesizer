"""Member repository — manages global team-member roles on the users table.

The `/admin/members` UI is a system-wide team view (not project-scoped), so it
operates on `users.role` rather than `project_members`. Per-project membership
lives in `project_members` and is handled separately by project-scoped flows.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.user import UserModel


VALID_ROLES = {"admin", "editor", "viewer"}


class MemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_dict(user: UserModel) -> dict:
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "added_at": user.created_at.isoformat() if user.created_at else "",
        }

    async def list_members(
        self, page: int = 1, page_size: int = 50
    ) -> tuple[list[dict], int]:
        query = (
            select(UserModel)
            .where(UserModel.is_active == True)
            .order_by(UserModel.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        count_query = select(func.count()).select_from(UserModel).where(
            UserModel.is_active == True
        )

        result = await self._session.execute(query)
        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one()

        members = [self._to_dict(u) for u in result.scalars().all()]
        return members, total

    async def get_member(self, member_id: uuid.UUID) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == member_id)
        )
        return result.scalar_one_or_none()

    async def find_user_by_email(self, email: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()

    async def create_member(self, user_id: uuid.UUID, role: str) -> dict:
        user = await self.get_member(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        user.role = role
        await self._session.flush()
        await self._session.refresh(user)
        return self._to_dict(user)

    async def update_member_role(
        self, member_id: uuid.UUID, role: str
    ) -> dict | None:
        user = await self.get_member(member_id)
        if not user:
            return None
        user.role = role
        await self._session.flush()
        await self._session.refresh(user)
        return self._to_dict(user)

    async def delete_member(self, member_id: uuid.UUID) -> bool:
        # Soft-remove: drop back to viewer rather than deleting the user record.
        user = await self.get_member(member_id)
        if not user:
            return False
        user.role = "viewer"
        await self._session.flush()
        return True
