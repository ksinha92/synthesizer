"""Masking repository ABC. No framework dependencies."""

from __future__ import annotations

import uuid
from abc import abstractmethod

from app.domain.masking.entities import MaskingPolicy, MaskingRule
from app.domain.shared.repository import Repository


class MaskingRepository(Repository[MaskingPolicy]):
    @abstractmethod
    async def find_by_project_id(self, project_id: uuid.UUID) -> list[MaskingPolicy]: ...

    @abstractmethod
    async def add_rule(self, rule: MaskingRule) -> MaskingRule: ...

    @abstractmethod
    async def get_rules_by_policy(self, policy_id: uuid.UUID) -> list[MaskingRule]: ...
