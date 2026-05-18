"""Connection command and query handlers."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import structlog

from app.domain.connection.entities import Connection
from app.domain.connection.repository import ConnectionRepository
from app.domain.connection.value_objects import (
    ConnectionCredentials,
    ConnectionStatus,
    ConnectorType,
)
from app.domain.shared.errors import NotFoundError
from app.infrastructure.connectors._retry import retry_async
from app.infrastructure.connectors._secrets import merge_preserving_secrets
from app.infrastructure.connectors.registry import ConnectorRegistry

from app.application.connection.commands import (
    CreateConnectionCommand,
    DeleteConnectionCommand,
    TestConnectionCommand,
    UpdateConnectionCommand,
)
from app.application.connection.queries import GetConnectionQuery, ListConnectionsQuery

logger = structlog.get_logger()


class CreateConnectionHandler:
    def __init__(self, repository: ConnectionRepository) -> None:
        self._repository = repository

    async def handle(self, command: CreateConnectionCommand) -> Connection:
        connection = Connection(
            project_id=command.project_id,
            name=command.name,
            connector_type=ConnectorType(command.connector_type),
            host=command.host,
            port=command.port,
            database_name=command.database_name,
            credentials=ConnectionCredentials(
                username=command.username,
                password=command.password,
            ),
            extra_params=command.extra_params,
            status=ConnectionStatus.UNTESTED,
        )
        saved = await self._repository.save(connection)
        await logger.ainfo(
            "connection_created",
            connection_id=str(saved.id),
            project_id=str(command.project_id),
            connector_type=command.connector_type,
        )
        return saved


class TestConnectionHandler:
    def __init__(self, repository: ConnectionRepository, registry: ConnectorRegistry) -> None:
        self._repository = repository
        self._registry = registry

    async def handle(self, command: TestConnectionCommand) -> tuple[bool, float]:
        connection = await self._repository.get(command.connection_id)
        if connection is None:
            raise NotFoundError(message=f"Connection {command.connection_id} not found")

        connector = self._registry.get_connector(
            connector_type=connection.connector_type,
            host=connection.host,
            port=connection.port,
            database_name=connection.database_name,
            username=connection.credentials.username,
            password=connection.credentials.password,
            extra_params=connection.extra_params,
        )

        start = time.monotonic()
        try:
            # Wrap test_connection in retry-with-backoff. We can only retry
            # on *transient* signals (warehouse cold-start, DNS blip, TCP
            # reset) — those manifest as exceptions raised by the underlying
            # connector. A plain ``False`` return means the connector itself
            # already classified the failure as permanent (bad creds,
            # missing DB) and swallowed the exception, so retrying just
            # burns 80 s of backoff for no signal change. Treat False as
            # the final answer; only raised exceptions go through retry.
            async def _attempt() -> bool:
                return await connector.test_connection()

            try:
                success = await retry_async(
                    _attempt,
                    connector=connection.connector_type.value,
                )
                if not isinstance(success, bool):
                    success = bool(success)
            except Exception:
                # Genuine transient exhaustion (after retry_async tried its
                # transient policy) or a permanent connector-level error.
                success = False
            latency = time.monotonic() - start

            connection.status = ConnectionStatus.CONNECTED if success else ConnectionStatus.FAILED
            connection.last_tested_at = datetime.now(timezone.utc)
            await self._repository.save(connection)

            await logger.ainfo(
                "connection_tested",
                connection_id=str(command.connection_id),
                success=success,
                latency_ms=round(latency * 1000),
            )
            return success, latency
        finally:
            await connector.close()


class UpdateConnectionHandler:
    def __init__(self, repository: ConnectionRepository) -> None:
        self._repository = repository

    async def handle(self, command: UpdateConnectionCommand) -> Connection:
        connection = await self._repository.get(command.connection_id)
        if connection is None:
            raise NotFoundError(message=f"Connection {command.connection_id} not found")

        if command.name is not None:
            connection.name = command.name
        if command.host is not None:
            connection.host = command.host
        if command.port is not None:
            connection.port = command.port
        if command.database_name is not None:
            connection.database_name = command.database_name
        if command.username is not None or command.password is not None:
            connection.credentials = ConnectionCredentials(
                username=command.username or connection.credentials.username,
                password=command.password or connection.credentials.password,
                extra=connection.credentials.extra,
            )
        if command.extra_params is not None:
            # Merge instead of overwriting so a partial edit (e.g. user
            # rotates the connection name only) doesn't wipe stored
            # secrets/extras the form rendered as redacted blanks.
            connection.extra_params = merge_preserving_secrets(
                connection.extra_params, command.extra_params
            )

        # Reset status when config changes
        connection.status = ConnectionStatus.UNTESTED

        return await self._repository.save(connection)


class DeleteConnectionHandler:
    def __init__(self, repository: ConnectionRepository) -> None:
        self._repository = repository

    async def handle(self, command: DeleteConnectionCommand) -> None:
        connection = await self._repository.get(command.connection_id)
        if connection is None:
            raise NotFoundError(message=f"Connection {command.connection_id} not found")
        await self._repository.delete(command.connection_id)
        await logger.ainfo("connection_deleted", connection_id=str(command.connection_id))


class GetConnectionHandler:
    def __init__(self, repository: ConnectionRepository) -> None:
        self._repository = repository

    async def handle(self, query: GetConnectionQuery) -> Connection:
        connection = await self._repository.get(query.connection_id)
        if connection is None:
            raise NotFoundError(message=f"Connection {query.connection_id} not found")
        return connection


class ListConnectionsHandler:
    def __init__(self, repository: ConnectionRepository) -> None:
        self._repository = repository

    async def handle(self, query: ListConnectionsQuery) -> tuple[list[Connection], int]:
        connections = await self._repository.find_by_project_id(
            query.project_id, query.limit, query.offset
        )
        total = await self._repository.count_by_project_id(query.project_id)
        return connections, total
