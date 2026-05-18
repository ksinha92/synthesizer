"""Connection CRUD, test, and schema introspection API endpoints."""

from __future__ import annotations

import asyncio
import socket
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.connection.commands import (
    CreateConnectionCommand,
    DeleteConnectionCommand,
    TestConnectionCommand,
    UpdateConnectionCommand,
)
from app.application.connection.handlers import (
    CreateConnectionHandler,
    DeleteConnectionHandler,
    GetConnectionHandler,
    ListConnectionsHandler,
    TestConnectionHandler,
    UpdateConnectionHandler,
)
from app.application.connection.queries import GetConnectionQuery, ListConnectionsQuery
from app.domain.connection.entities import Connection
from app.domain.connection.value_objects import ConnectorType
from app.domain.shared.errors import NotFoundError
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rate_limit import rate_limit
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.connectors._secrets import redact
from app.infrastructure.connectors.registry import CONNECTOR_METADATA, create_registry
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.connection_repo import SQLAlchemyConnectionRepository

logger = structlog.get_logger()

router = APIRouter(
    prefix="/projects/{project_id}/connections",
    tags=["connections"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


# --- Request/Response Models ---


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    connector_type: str
    host: str = Field("", max_length=255)
    port: int = Field(..., ge=1, le=65535)
    database_name: str = Field(..., min_length=1, max_length=255)
    username: str = Field("", max_length=255)
    password: str = Field("", max_length=1024)
    extra_params: dict = Field(default_factory=dict)

    @field_validator("connector_type")
    @classmethod
    def _validate_connector_type(cls, v: str) -> str:
        valid = {c.value for c in ConnectorType}
        if v not in valid:
            raise ValueError(f"Unsupported connector_type '{v}'. Valid: {sorted(valid)}")
        return v


class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    database_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=1024)
    extra_params: dict | None = None


class ConnectionResponse(BaseModel):
    """Connection response — credentials are NEVER included.

    ``safe_extras`` is the persisted ``extra_params`` with secret keys
    (tokens, passphrases, private keys) replaced by empty strings. The
    edit form uses these to repopulate non-secret config so an edit-save
    on one field doesn't wipe the rest. Submitting an empty string for a
    secret key tells the backend to preserve its stored value.
    """

    id: str
    project_id: str
    name: str
    connector_type: str
    host: str
    port: int
    database_name: str
    username: str
    status: str
    last_tested_at: str | None
    created_at: str
    updated_at: str
    safe_extras: dict = Field(default_factory=dict)


class ConnectionListResponse(BaseModel):
    items: list[ConnectionResponse]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class ConnectionTestResponse(BaseModel):
    success: bool
    status: str
    latency_ms: int
    message: str | None = None


class SchemaResponse(BaseModel):
    schemas: list[dict]


class TableResponse(BaseModel):
    schema_name: str
    tables: list[dict]


class ColumnResponse(BaseModel):
    schema_name: str
    table_name: str
    columns: list[dict]


class ConnectorMetadataResponse(BaseModel):
    connectors: list[dict]


class PreflightRequest(BaseModel):
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(..., ge=1, le=65535)


class PreflightResponse(BaseModel):
    dns_resolved: bool
    port_reachable: bool
    detail: str


# --- Endpoints ---


@router.get("/metadata", response_model=ConnectorMetadataResponse)
async def get_connector_metadata(
    project_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    _member: dict = Depends(require_project_membership("viewer")),
):
    """Return the catalogue of supported connectors + their config schema.

    The frontend tile grid + dynamic field rendering reads from this so the
    UI never falls out of sync with the backend's registry.
    """
    return ConnectorMetadataResponse(
        connectors=[{"type": k, **v} for k, v in CONNECTOR_METADATA.items()]
    )


@router.post("/preflight", response_model=PreflightResponse)
async def preflight_connection(
    project_id: uuid.UUID,
    body: PreflightRequest,
    current_user: dict = Depends(get_current_user),
    _member: dict = Depends(require_project_membership("editor")),
    _rl: None = Depends(rate_limit(per_min=5)),
):
    """Resolve DNS + check port reachability before saving a connection."""
    dns_ok = False
    port_ok = False
    detail = ""
    try:
        loop = asyncio.get_event_loop()
        await loop.getaddrinfo(body.host, body.port)
        dns_ok = True
    except Exception as e:
        return PreflightResponse(dns_resolved=False, port_reachable=False, detail=f"DNS failure: {e}")

    try:
        fut = asyncio.open_connection(body.host, body.port)
        reader, writer = await asyncio.wait_for(fut, timeout=3.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        port_ok = True
        detail = "ok"
    except asyncio.TimeoutError:
        detail = f"Port {body.port} on {body.host} did not respond within 3s"
    except OSError as e:
        detail = f"Port {body.port} on {body.host} refused connection: {e}"

    return PreflightResponse(dns_resolved=dns_ok, port_reachable=port_ok, detail=detail)


@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    project_id: uuid.UUID,
    body: ConnectionCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemyConnectionRepository(session)
    handler = CreateConnectionHandler(repo)

    command = CreateConnectionCommand(
        project_id=project_id,
        name=body.name,
        connector_type=body.connector_type,
        host=body.host,
        port=body.port,
        database_name=body.database_name,
        username=body.username,
        password=body.password,
        extra_params=body.extra_params,
    )

    connection = await handler.handle(command)

    await logger.ainfo(
        "connection_created",
        connection_id=str(connection.id),
        project_id=str(project_id),
        user_id=current_user["id"],
        ip=request.client.host if request.client else "unknown",
    )

    return _connection_response(connection)


@router.get("", response_model=ConnectionListResponse)
async def list_connections(
    project_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = SQLAlchemyConnectionRepository(session)
    handler = ListConnectionsHandler(repo)

    offset = (page - 1) * page_size
    query = ListConnectionsQuery(project_id=project_id, limit=page_size, offset=offset)
    connections, total = await handler.handle(query)

    return ConnectionListResponse(
        items=[_connection_response(c) for c in connections],
        total_count=total,
        page=page,
        page_size=page_size,
        has_more=(offset + page_size) < total,
    )


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    repo = SQLAlchemyConnectionRepository(session)
    handler = GetConnectionHandler(repo)

    try:
        connection = await handler.handle(GetConnectionQuery(connection_id=connection_id))
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})

    if connection.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})

    return _connection_response(connection)


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    body: ConnectionUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemyConnectionRepository(session)

    # Verify connection belongs to project
    get_handler = GetConnectionHandler(repo)
    try:
        existing = await get_handler.handle(GetConnectionQuery(connection_id=connection_id))
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})

    if existing.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})

    handler = UpdateConnectionHandler(repo)
    command = UpdateConnectionCommand(
        connection_id=connection_id,
        name=body.name,
        host=body.host,
        port=body.port,
        database_name=body.database_name,
        username=body.username,
        password=body.password,
        extra_params=body.extra_params,
    )
    connection = await handler.handle(command)
    return _connection_response(connection)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemyConnectionRepository(session)

    get_handler = GetConnectionHandler(repo)
    try:
        existing = await get_handler.handle(GetConnectionQuery(connection_id=connection_id))
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})

    if existing.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})

    handler = DeleteConnectionHandler(repo)
    await handler.handle(DeleteConnectionCommand(connection_id=connection_id))

    await logger.ainfo(
        "connection_deleted",
        connection_id=str(connection_id),
        project_id=str(project_id),
        user_id=current_user["id"],
        ip=request.client.host if request.client else "unknown",
    )


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("editor")),
):
    repo = SQLAlchemyConnectionRepository(session)
    registry = create_registry()
    handler = TestConnectionHandler(repo, registry)

    try:
        success, latency = await handler.handle(TestConnectionCommand(connection_id=connection_id))
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})

    await logger.ainfo(
        "connection_tested",
        connection_id=str(connection_id),
        project_id=str(project_id),
        user_id=current_user["id"],
        success=success,
        ip=request.client.host if request.client else "unknown",
    )

    return ConnectionTestResponse(
        success=success,
        status="connected" if success else "failed",
        latency_ms=round(latency * 1000),
        message="Connection verified" if success else "Test failed — check credentials, host reachability, and SSL configuration.",
    )


@router.get("/{connection_id}/schemas", response_model=SchemaResponse)
async def get_schemas(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    connection = await _get_connection_or_404(session, project_id, connection_id)

    registry = create_registry()
    connector = _build_connector(registry, connection)
    try:
        schemas = await connector.get_schemas()
    finally:
        await connector.close()

    await logger.ainfo(
        "schema_introspected",
        connection_id=str(connection_id),
        project_id=str(project_id),
        user_id=current_user["id"],
        schema_count=len(schemas),
        ip=request.client.host if request.client else "unknown",
    )

    return SchemaResponse(schemas=schemas)


@router.get("/{connection_id}/schemas/{schema_name}/tables", response_model=TableResponse)
async def get_tables(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    schema_name: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    connection = await _get_connection_or_404(session, project_id, connection_id)
    registry = create_registry()
    connector = _build_connector(registry, connection)
    try:
        tables = await connector.get_tables(schema_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "schema_not_found", "detail": str(e)})
    finally:
        await connector.close()
    return TableResponse(schema_name=schema_name, tables=tables)


@router.get(
    "/{connection_id}/schemas/{schema_name}/tables/{table_name}/columns",
    response_model=ColumnResponse,
)
async def get_columns(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    schema_name: str,
    table_name: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _member: dict = Depends(require_project_membership("viewer")),
):
    connection = await _get_connection_or_404(session, project_id, connection_id)
    registry = create_registry()
    connector = _build_connector(registry, connection)
    try:
        columns = await connector.get_columns(schema_name, table_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "table_not_found", "detail": str(e)})
    finally:
        await connector.close()
    return ColumnResponse(schema_name=schema_name, table_name=table_name, columns=columns)


# --- Helpers ---


def _connection_response(connection: Connection) -> ConnectionResponse:
    """Map domain entity to response — NEVER include credentials.

    Username is returned (it's the identity, not the secret) so the edit
    form can repopulate it. The actual password / tokens flow via
    ``safe_extras`` with secrets redacted.
    """
    return ConnectionResponse(
        id=str(connection.id),
        project_id=str(connection.project_id),
        name=connection.name,
        connector_type=connection.connector_type.value,
        host=connection.host,
        port=connection.port,
        database_name=connection.database_name,
        username=connection.credentials.username,
        status=connection.status.value,
        last_tested_at=connection.last_tested_at.isoformat() if connection.last_tested_at else None,
        created_at=connection.created_at.isoformat() if connection.created_at else "",
        updated_at=connection.updated_at.isoformat() if connection.updated_at else "",
        safe_extras=redact(connection.extra_params),
    )


async def _get_connection_or_404(
    session: AsyncSession,
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> Connection:
    repo = SQLAlchemyConnectionRepository(session)
    get_handler = GetConnectionHandler(repo)
    try:
        connection = await get_handler.handle(GetConnectionQuery(connection_id=connection_id))
    except NotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})
    if connection.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Connection not found"})
    return connection


def _build_connector(registry, connection: Connection):
    return registry.get_connector(
        connector_type=connection.connector_type,
        host=connection.host,
        port=connection.port,
        database_name=connection.database_name,
        username=connection.credentials.username,
        password=connection.credentials.password,
        extra_params=connection.extra_params,
    )
