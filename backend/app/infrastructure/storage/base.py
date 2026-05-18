"""Storage backend abstraction."""

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, path: str, data: bytes) -> str: ...

    @abstractmethod
    async def load(self, path: str) -> bytes: ...

    @abstractmethod
    async def delete(self, path: str) -> None: ...

    @abstractmethod
    async def list(self, prefix: str = "") -> list[str]: ...

    @abstractmethod
    async def get_url(self, path: str) -> str: ...
