"""Connection domain services. No framework dependencies."""

from __future__ import annotations

from app.domain.connection.entities import Connection
from app.domain.connection.events import ConnectionFailed, ConnectionTested
from app.domain.connection.value_objects import ConnectionStatus


class ConnectionTestService:
    """Tests a connection and updates its status. Actual connector logic is injected."""

    async def test_connection(self, connection: Connection) -> bool:
        # Placeholder — actual connector implementation injected in infrastructure layer
        try:
            # Infrastructure connector will be injected here in Phase 3
            connection.status = ConnectionStatus.CONNECTED
            connection.add_event(ConnectionTested(aggregate_id=connection.id))
            return True
        except Exception:
            connection.status = ConnectionStatus.FAILED
            connection.add_event(ConnectionFailed(aggregate_id=connection.id))
            return False
