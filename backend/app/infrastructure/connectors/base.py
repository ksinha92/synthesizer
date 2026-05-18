"""Base connector abstraction for all data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Abstract base for all data source connectors.

    Each connector implements introspection and data access for a specific
    database type. Connectors use raw async drivers (not SQLAlchemy) for
    direct access to information_schema and system catalogs.
    """

    def __init__(
        self,
        host: str,
        port: int,
        database_name: str,
        username: str = "",
        password: str = "",
        extra_params: dict[str, Any] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._database_name = database_name
        self._username = username
        self._password = password
        self._extra_params = extra_params or {}

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connectivity. Returns True if reachable, False otherwise."""
        ...

    @abstractmethod
    async def get_schemas(self) -> list[dict[str, Any]]:
        """List available schemas. Returns [{"name": "public"}, ...]."""
        ...

    @abstractmethod
    async def get_tables(self, schema: str) -> list[dict[str, Any]]:
        """List tables in a schema. Returns [{"name": "users", "row_count": 100, "size_bytes": 8192}, ...]."""
        ...

    @abstractmethod
    async def get_columns(self, schema: str, table: str) -> list[dict[str, Any]]:
        """List columns in a table. Returns column metadata dicts."""
        ...

    @abstractmethod
    async def get_sample_data(self, schema: str, table: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch sample rows from a table. Must validate schema/table names against information_schema."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release all connections and resources."""
        ...
