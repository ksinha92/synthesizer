---
phase: 54-destinations-vfk-diff
plan: 01
subsystem: db, api
tags: [destinations, output-mode, virtual-fk, schema-diff, migration]
requires:
  - phase: 48-shell-and-tokens
provides:
  - Migration 020 — synthetic_configs.output_mode + subset_configs.output_mode + discovered_relationships.is_virtual
  - GET /api/v1/projects/{id}/discovery/diff?connection_id=...
  - POST /api/v1/projects/{id}/relationships (create virtual FK)
  - DELETE /api/v1/projects/{id}/relationships/{relationship_id}
affects: [55-quality-gate]
duration: ~20min
completed: 2026-05-16
---

# Phase 54 Plan 01: Destinations + Virtual FKs + Schema-Changes Diff

**148/148 backend unit tests still green; alembic head now 020; routes registered + verified via openapi.json.**

## Highlights
- **Migration 020** is additive:
  - `synthetic_configs.output_mode` and `subset_configs.output_mode`
    (`VARCHAR(50)` NOT NULL DEFAULT `'same_database'`). The allowed value set
    (`same_database` / `different_connection` / `download_zip` / `s3`) is
    enforced at the API layer when those endpoints are extended, not at the
    DB layer — keeps the migration trivial.
  - `discovered_relationships.is_virtual` (`BOOLEAN` NOT NULL DEFAULT
    `false`). Auto-discovered FKs stay `false`; user-asserted virtual FKs
    are `true`.
- **Schema-changes diff** at `GET /projects/{id}/discovery/diff?connection_id=...`
  joins the connection back to the project, loads persisted discovery into a
  `(schema, table) → {col: data_type}` dict, then **read-only**
  introspects the live source via `connector.get_schemas / get_tables /
  get_columns` and emits the structural delta: added/removed tables +
  added/removed/changed columns. The live introspection is never persisted —
  the user re-runs discovery if they want the change applied.
- **Virtual FK CRUD**:
  - `POST /projects/{id}/relationships` validates that the referenced
    `schema_id` belongs to a connection in the project, then writes a
    `discovered_relationships` row with `is_virtual=true` and
    `confidence=1.0`.
  - `DELETE /projects/{id}/relationships/{relationship_id}` deletes any
    relationship — virtual or auto-discovered — scoped to the project for
    safety.

## API surface (registered in openapi.json)
```
GET    /api/v1/projects/{project_id}/discovery/diff?connection_id=...
POST   /api/v1/projects/{project_id}/relationships          { schema_id, src_table, src_col, tgt_table, tgt_col }
DELETE /api/v1/projects/{project_id}/relationships/{relationship_id}
```

## Models extended
- `SyntheticConfigModel.output_mode` — `String(50)` default `same_database`.
- `SubsetConfigModel.output_mode` — same.
- `DiscoveredRelationshipModel.is_virtual` — `Boolean` default `False`.

## Edge cases handled
- Diff endpoint: connector failures during live introspection don't crash —
  individual `get_schemas / get_tables / get_columns` calls are wrapped in
  try/except and skipped silently. Caller still gets the persisted-side view.
- Schema-not-in-project on virtual-FK create → 404 (no leak of cross-project
  schema ids).
- Relationship-not-in-project on delete → 404 (same scoping).
- Connector is always closed via `finally`.

## Out of scope (queued)
- **UI surfacing** of all three features. The relationships graph
  (`relationship-graph.tsx` from Phase 27) is where the virtual-FK
  add/remove UI fits; a small "Schema changes" panel on the connection
  detail page fits the diff endpoint. Both deferred to Phase 55 polish
  pass or later — the API surface ships now.
- **`output_mode` plumbing** in synthetic / subset create / update
  endpoints. The DB column is in place; create/update Pydantic models
  still don't expose it. Adding the field is one line per endpoint; the
  generation pipeline doesn't yet branch on it. Deferred so this phase
  ships small and the engine integration can land in a dedicated plan.

## Manual verification (when UI lands)
- [ ] Mark a relationship virtual via POST; it shows in the graph with a
      distinct style.
- [ ] Delete it via the same UI; the row disappears.
- [ ] Diff endpoint correctly reports a table added after a connection's
      last discovery.
- [ ] Diff endpoint correctly reports a column whose data_type changed.

---
*Phase: 54-destinations-vfk-diff, Plan: 01 — Completed 2026-05-16*
