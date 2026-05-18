"""Synthetic repository ABC. No framework dependencies."""

from __future__ import annotations

import uuid
from abc import abstractmethod

from app.domain.shared.repository import Repository
from app.domain.synthetic.entities import SyntheticConfig


class SyntheticRepository(Repository[SyntheticConfig]):

    @abstractmethod
    async def find_by_project_id(self, project_id: uuid.UUID) -> list[SyntheticConfig]:
        ...
