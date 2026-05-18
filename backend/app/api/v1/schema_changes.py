"""Schema-changes diff + virtual-FK endpoints (Phase 54).

Two complementary surfaces for the discovery experience:

- ``GET /api/v1/projects/{project_id}/discovery/diff?connection_id=...``
  compares the most recently persisted discovery for a connection against
  a fresh, **read-only** live introspection. Returns the structural delta
  so users can decide whether to re-run discovery.

- ``POST / DELETE /api/v1/projects/{project_id}/relationships`` create or
  remove a user-asserted virtual FK in ``discovered_relationships``.
  ``is_virtual=true`` is the only differentiator from auto-discovered FKs.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import require_project_membership
from app.infrastructure.connectors.registry import create_registry
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.connection import ConnectionModel
from app.infrastructure.persistence.models.discovery import (
    DiscoveredColumnModel,
    DiscoveredRelationshipModel,
    DiscoveredSchemaModel,
    DiscoveredTableModel,
)
from app.infrastructure.persistence.sqlalchemy.connection_repo import _decrypt_credentials
from app.domain.connection.value_objects import ConnectorType

logger = structlog.get_logger()
router = APIRouter(
    prefix="/projects/{project_id}",
    tags=["schema-changes"],
    dependencies=[Depends(require_project_membership("viewer"))],
)


# ─── Schema-changes diff ────────────────────────────────────────────────────


class TableDiff(BaseModel):
    table_name: str
    schema_name: str
    change: str  # "added" | "removed"


class ColumnDiff(BaseModel):
    schema_name: str
    table_name: str
    column_name: str
    change: str  # "added" | "removed" | "type_changed"
    old_data_type: str | None = None
    new_data_type: str | None = None


class SchemaDiffResponse(BaseModel):
    connection_id: str
    last_discovered_at: str | None
    added_tables: list[TableDiff]
    removed_tables: list[TableDiff]
    added_columns: list[ColumnDiff]
    removed_columns: list[ColumnDiff]
    changed_columns: list[ColumnDiff]


@router.get("/discovery/diff", response_model=SchemaDiffResponse)
async def discovery_diff(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Compare persisted discovery vs a fresh live introspection.

    Read-only: the live introspection is NOT persisted. Re-run discovery to
    apply changes.
    """
    conn_result = await session.execute(
        select(ConnectionModel).where(
            ConnectionModel.id == connection_id,
            ConnectionModel.project_id == project_id,
        )
    )
    connection = conn_result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Connection not in project"})

    # Persisted state — load only the schemas saved by the most recent
    # discovery run for this connection. ``discovered_schemas`` is
    # append-only, so the previous query was either (a) unioning every
    # historical snapshot (stale tables would be reported as still present)
    # or (b) keeping the latest per schema_name (stale schema_names dropped
    # by the most recent run would still leak through). The correct
    # behaviour is "show me the latest discovery batch as a whole".
    #
    # We use MAX(discovered_at) for the connection and include every row
    # sharing that timestamp. That handles both the current discovery
    # service (one row per run) and a future service that writes one row
    # per schema_name in a single batch.
    latest_ts_q = await session.execute(
        select(func.max(DiscoveredSchemaModel.discovered_at))
        .where(DiscoveredSchemaModel.connection_id == connection_id)
    )
    last_seen = latest_ts_q.scalar()
    persisted: dict[tuple[str, str], dict[str, str]] = {}  # (schema, table) → {col: data_type}

    if last_seen is not None:
        schemas_q = await session.execute(
            select(DiscoveredSchemaModel).where(
                DiscoveredSchemaModel.connection_id == connection_id,
                DiscoveredSchemaModel.discovered_at == last_seen,
            )
        )
        for schema in schemas_q.scalars().all():
            tables_q = await session.execute(
                select(DiscoveredTableModel).where(DiscoveredTableModel.schema_id == schema.id)
            )
            for table in tables_q.scalars().all():
                cols_q = await session.execute(
                    select(DiscoveredColumnModel).where(
                        DiscoveredColumnModel.table_id == table.id
                    )
                )
                persisted[(schema.schema_name, table.table_name)] = {
                    col.column_name: col.data_type for col in cols_q.scalars().all()
                }

    # Live introspection — read-only.
    creds = _decrypt_credentials(connection.credentials or {})
    registry = create_registry()
    connector = registry.get_connector(
        connector_type=ConnectorType(connection.connector_type),
        host=connection.host,
        port=connection.port,
        database_name=connection.database_name,
        username=creds.get("username", ""),
        password=creds.get("password", ""),
        extra_params=connection.extra_params or {},
    )

    live: dict[tuple[str, str], dict[str, str]] = {}
    try:
        try:
            live_schemas = await connector.get_schemas()
        except Exception as e:
            await logger.awarning("schema_diff_get_schemas_failed", error=str(e))
            live_schemas = []

        for s in live_schemas:
            sname = s["name"]
            try:
                live_tables = await connector.get_tables(sname)
            except Exception as exc:
                # Skip the schema rather than failing the whole diff — partial
                # results are more useful than no results when a few schemas
                # are inaccessible (perms, transient errors, etc.).
                await logger.awarning(
                    "schema_diff_get_tables_failed",
                    schema=sname,
                    error=type(exc).__name__,
                    connection_id=str(connection_id),
                )
                continue
            for tinfo in live_tables:
                tname = tinfo.get("name") if isinstance(tinfo, dict) else tinfo
                if not tname:
                    continue
                try:
                    cols = await connector.get_columns(sname, tname)
                except Exception as exc:
                    await logger.awarning(
                        "schema_diff_get_columns_failed",
                        schema=sname,
                        table=tname,
                        error=type(exc).__name__,
                        connection_id=str(connection_id),
                    )
                    continue
                live[(sname, tname)] = {
                    c.get("name", ""): c.get("data_type", "") for c in cols
                }
    finally:
        try:
            await connector.close()
        except Exception as exc:
            # Connector close is best-effort — the request has already been
            # served; surface as info so leaks show up in dashboards without
            # alarming on every transient.
            await logger.ainfo(
                "schema_diff_connector_close_failed",
                error=type(exc).__name__,
                connection_id=str(connection_id),
            )

    persisted_tables = set(persisted.keys())
    live_tables = set(live.keys())

    added_tables = [
        TableDiff(schema_name=s, table_name=t, change="added")
        for (s, t) in sorted(live_tables - persisted_tables)
    ]
    removed_tables = [
        TableDiff(schema_name=s, table_name=t, change="removed")
        for (s, t) in sorted(persisted_tables - live_tables)
    ]

    added_columns: list[ColumnDiff] = []
    removed_columns: list[ColumnDiff] = []
    changed_columns: list[ColumnDiff] = []

    for key in persisted_tables & live_tables:
        sname, tname = key
        old_cols = persisted[key]
        new_cols = live[key]
        for cname in sorted(set(new_cols) - set(old_cols)):
            added_columns.append(
                ColumnDiff(
                    schema_name=sname, table_name=tname, column_name=cname,
                    change="added", new_data_type=new_cols[cname],
                )
            )
        for cname in sorted(set(old_cols) - set(new_cols)):
            removed_columns.append(
                ColumnDiff(
                    schema_name=sname, table_name=tname, column_name=cname,
                    change="removed", old_data_type=old_cols[cname],
                )
            )
        for cname in sorted(set(old_cols) & set(new_cols)):
            if old_cols[cname] != new_cols[cname]:
                changed_columns.append(
                    ColumnDiff(
                        schema_name=sname, table_name=tname, column_name=cname,
                        change="type_changed",
                        old_data_type=old_cols[cname], new_data_type=new_cols[cname],
                    )
                )

    return SchemaDiffResponse(
        connection_id=str(connection_id),
        last_discovered_at=last_seen.isoformat() if last_seen else None,
        added_tables=added_tables,
        removed_tables=removed_tables,
        added_columns=added_columns,
        removed_columns=removed_columns,
        changed_columns=changed_columns,
    )


# ─── Virtual FK CRUD ────────────────────────────────────────────────────────


class VirtualFKCreate(BaseModel):
    schema_id: str
    source_table_id: str
    source_column_id: str
    target_table_id: str
    target_column_id: str
    relationship_type: str = "many_to_one"


class VirtualFKResponse(BaseModel):
    id: str
    schema_id: str
    source_table_id: str
    source_column_id: str
    target_table_id: str
    target_column_id: str
    relationship_type: str
    confidence: float
    is_virtual: bool


@router.post("/relationships", response_model=VirtualFKResponse, status_code=201)
async def create_virtual_fk(
    project_id: uuid.UUID,
    body: VirtualFKCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a user-asserted virtual FK in discovered_relationships.

    The schema must belong to a connection in this project. Identity of the
    rest of the references is trusted to the caller (frontend looks them up
    from a single discovered schema before posting).
    """
    schema_uuid = uuid.UUID(body.schema_id)
    schema_result = await session.execute(
        select(DiscoveredSchemaModel)
        .join(ConnectionModel, ConnectionModel.id == DiscoveredSchemaModel.connection_id)
        .where(
            DiscoveredSchemaModel.id == schema_uuid,
            ConnectionModel.project_id == project_id,
        )
    )
    if schema_result.scalar_one_or_none() is None:
        raise HTTPException(404, {"error": "not_found", "detail": "Schema not in this project"})

    rel = DiscoveredRelationshipModel(
        id=uuid.uuid4(),
        schema_id=schema_uuid,
        source_table_id=uuid.UUID(body.source_table_id),
        source_column_id=uuid.UUID(body.source_column_id),
        target_table_id=uuid.UUID(body.target_table_id),
        target_column_id=uuid.UUID(body.target_column_id),
        relationship_type=body.relationship_type,
        confidence=1.0,
        is_virtual=True,
    )
    session.add(rel)
    await session.flush()
    await logger.ainfo(
        "virtual_fk_created", relationship_id=str(rel.id), project_id=str(project_id)
    )
    return VirtualFKResponse(
        id=str(rel.id),
        schema_id=str(rel.schema_id),
        source_table_id=str(rel.source_table_id),
        source_column_id=str(rel.source_column_id),
        target_table_id=str(rel.target_table_id),
        target_column_id=str(rel.target_column_id),
        relationship_type=rel.relationship_type,
        confidence=rel.confidence,
        is_virtual=rel.is_virtual,
    )


@router.delete("/relationships/{relationship_id}", status_code=204)
async def delete_relationship(
    project_id: uuid.UUID,
    relationship_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a relationship (virtual or auto-discovered).

    Restricted to relationships whose schema belongs to a connection in
    this project.
    """
    lookup = await session.execute(
        select(DiscoveredRelationshipModel, DiscoveredSchemaModel.connection_id)
        .join(
            DiscoveredSchemaModel,
            DiscoveredSchemaModel.id == DiscoveredRelationshipModel.schema_id,
        )
        .join(
            ConnectionModel,
            ConnectionModel.id == DiscoveredSchemaModel.connection_id,
        )
        .where(
            DiscoveredRelationshipModel.id == relationship_id,
            ConnectionModel.project_id == project_id,
        )
    )
    row = lookup.first()
    if row is None:
        raise HTTPException(
            404, {"error": "not_found", "detail": "Relationship not in this project"}
        )

    await session.execute(
        delete(DiscoveredRelationshipModel).where(
            DiscoveredRelationshipModel.id == relationship_id
        )
    )
    await session.flush()
    await logger.ainfo(
        "relationship_deleted",
        relationship_id=str(relationship_id),
        project_id=str(project_id),
    )
