"""Shared masking helpers consumed by Database View, Privacy Hub, and Presets.

These used to live as private helpers on ``privacy_hub.py`` and a duplicated
``GENERATOR_CHOICES`` list on ``database_view.py``. Pulling them into one
module removes the cross-router private import and the drift risk of having
two enum constants that always have to stay in lockstep.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.masking import MaskingPolicyModel


# Built-in generator vocabulary. Mirrors what the masking engine supports
# today. The Presets router uses a set form (``ALLOWED_GENERATOR_TYPES``)
# for fast membership checks; both wrap the same source of truth.
GENERATOR_CHOICES: list[str] = [
    "hash",
    "redact",
    "faker_replace",
    "shuffle",
    "nullify",
    "fpe",
    "passthrough",
]

ALLOWED_GENERATOR_TYPES: set[str] = set(GENERATOR_CHOICES)


async def get_or_create_default_policy(
    session: AsyncSession, project_id: uuid.UUID
) -> uuid.UUID:
    """Return the project's default masking policy id, creating one if missing."""
    existing = await session.execute(
        select(MaskingPolicyModel).where(
            MaskingPolicyModel.project_id == project_id,
            MaskingPolicyModel.is_default == True,  # noqa: E712
        )
    )
    policy = existing.scalar_one_or_none()
    if policy is not None:
        return policy.id

    policy = MaskingPolicyModel(
        id=uuid.uuid4(),
        project_id=project_id,
        name="Default",
        description="Auto-created by Privacy Hub apply-all",
        is_default=True,
    )
    session.add(policy)
    await session.flush()
    return policy.id
