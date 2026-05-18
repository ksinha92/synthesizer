"""Base value object for domain layer. No framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Immutable value object. Equality is based on all fields."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))
