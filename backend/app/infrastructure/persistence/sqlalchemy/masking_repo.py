"""SQLAlchemy masking repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.masking.entities import MaskingPolicy, MaskingRule
from app.domain.masking.repository import MaskingRepository
from app.domain.masking.value_objects import MaskingStrategy
from app.infrastructure.persistence.models.masking import MaskingPolicyModel, MaskingRuleModel


class SQLAlchemyMaskingRepository(MaskingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: uuid.UUID) -> MaskingPolicy | None:
        result = await self._session.execute(select(MaskingPolicyModel).where(MaskingPolicyModel.id == entity_id))
        m = result.scalar_one_or_none()
        return self._policy_to_entity(m) if m else None

    async def save(self, entity: MaskingPolicy) -> MaskingPolicy:
        model = MaskingPolicyModel(id=entity.id, project_id=entity.project_id, name=entity.name, description=entity.description, is_default=entity.is_default)
        self._session.add(model)
        await self._session.flush()
        return self._policy_to_entity(model)

    async def delete(self, entity_id: uuid.UUID) -> None:
        pass

    async def list(self, limit=100, offset=0) -> list[MaskingPolicy]:
        result = await self._session.execute(select(MaskingPolicyModel).limit(limit).offset(offset))
        return [self._policy_to_entity(m) for m in result.scalars().all()]

    async def find_by_project_id(self, project_id: uuid.UUID) -> list[MaskingPolicy]:
        result = await self._session.execute(
            select(MaskingPolicyModel).where(MaskingPolicyModel.project_id == project_id).order_by(MaskingPolicyModel.created_at.desc())
        )
        return [self._policy_to_entity(m) for m in result.scalars().all()]

    async def add_rule(self, rule: MaskingRule) -> MaskingRule:
        model = MaskingRuleModel(
            id=rule.id, policy_id=rule.policy_id, column_id=rule.column_id,
            match_pattern=rule.match_pattern, masking_type=rule.masking_type.value,
            masking_config=rule.masking_config, preserve_format=rule.preserve_format, deterministic=rule.deterministic,
            preset_id=rule.preset_id,
            linked_column_ids=list(rule.linked_column_ids) if rule.linked_column_ids else None,
            consistency_group=rule.consistency_group,
        )
        self._session.add(model)
        await self._session.flush()
        return self._rule_to_entity(model)

    async def update_rule(self, rule_id: uuid.UUID, policy_id: uuid.UUID, updates: dict) -> dict | None:
        result = await self._session.execute(
            select(MaskingRuleModel).where(MaskingRuleModel.id == rule_id, MaskingRuleModel.policy_id == policy_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        for key, value in updates.items():
            if hasattr(model, key):
                setattr(model, key, value)
        await self._session.flush()
        return {
            "id": str(model.id), "policy_id": str(model.policy_id),
            "masking_type": model.masking_type, "masking_config": model.masking_config or {},
            "preserve_format": model.preserve_format, "deterministic": model.deterministic,
            "linked_column_ids": [str(c) for c in (model.linked_column_ids or [])],
            "consistency_group": model.consistency_group,
        }

    async def delete_rule(self, rule_id: uuid.UUID, policy_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(MaskingRuleModel).where(MaskingRuleModel.id == rule_id, MaskingRuleModel.policy_id == policy_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def get_rules_by_policy(self, policy_id: uuid.UUID) -> list[MaskingRule]:
        result = await self._session.execute(select(MaskingRuleModel).where(MaskingRuleModel.policy_id == policy_id))
        return [self._rule_to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _policy_to_entity(m: MaskingPolicyModel) -> MaskingPolicy:
        return MaskingPolicy(id=m.id, project_id=m.project_id, name=m.name, description=m.description, is_default=m.is_default, created_at=m.created_at, updated_at=m.updated_at)

    @staticmethod
    def _rule_to_entity(m: MaskingRuleModel) -> MaskingRule:
        return MaskingRule(
            id=m.id, policy_id=m.policy_id, column_id=m.column_id,
            match_pattern=m.match_pattern, masking_type=MaskingStrategy(m.masking_type),
            masking_config=m.masking_config or {},
            preserve_format=m.preserve_format, deterministic=m.deterministic,
            preset_id=getattr(m, "preset_id", None),
            linked_column_ids=list(getattr(m, "linked_column_ids", None) or []),
            consistency_group=getattr(m, "consistency_group", None),
            created_at=m.created_at, updated_at=m.updated_at,
        )
