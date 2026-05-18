"""Synthetic engine ABC. No framework dependencies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.synthetic.entities import SyntheticConfig


class BaseSyntheticEngine(ABC):
    """Abstract synthetic data engine. Infrastructure provides implementations."""

    @abstractmethod
    async def generate(
        self, config: SyntheticConfig, schema_metadata: dict
    ) -> dict[str, list[dict]]:
        """Generate data for all tables. Returns {table_name: [row_dicts]}."""
        ...

    @abstractmethod
    async def preview(
        self, config: SyntheticConfig, schema_metadata: dict, limit: int = 10
    ) -> dict[str, list[dict]]:
        """Preview a small sample. Returns {table_name: [row_dicts]}."""
        ...
