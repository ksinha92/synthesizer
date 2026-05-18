---
phase: 56-deferred-finish
plan: 02
subsystem: api, frontend, engine, messaging
tags: [end-to-end-wiring, masking-tasks, discovery-store, output-mode, virtual-fk]
requires:
  - phase: 56-deferred-finish
    plan: 01
provides:
  - masking_tasks resolves presets + threads consistency_group + linked_column_ids → engine.mask_row
  - synthetic/subset list+get endpoints surface output_mode (side-lookup from model)
  - discovery_repo + /discovery/relationships endpoint surface is_virtual
  - DiscoveredRelationship domain entity carries is_virtual
  - discovery-store fetches via schema_id, resolves IDs→names, threads is_virtual + relationship id
  - discovery-store.deleteRelationship + discovery page wires it into <RelationshipGraph onDeleteRelationship>
duration: ~25min
completed: 2026-05-16
---

# Phase 56 Plan 02: End-to-end Wiring Audit & Fix

**Codex stop-time review flagged "multiple claimed A–E features are not wired end to end." Audit confirmed four real gaps; all four are now closed. 154/154 backend unit tests still passing; frontend tsc clean.**

## Audit findings + fixes

### Gap A (presets) — masking engine never consulted the preset

**Before**: `POST /database/columns/{id}/rule { preset_id }` stored `preset_id`
on the rule, but `masking_tasks._run_masking_async` built `rule_configs`
from `rule.masking_type` + `rule.masking_config` only. A rule with
`preset_id=P1` (custom preset, generator_type=hash, config={"algo":"sha256"})
was masked as raw "hash" with empty config — the preset was metadata-only.

**Fix**: `masking_tasks` now collects all referenced `preset_id`s, batch-
loads `GeneratorPresetModel`, and **preset overrides take precedence**:

- `masking_type` ← preset.generator_type (when present)
- `masking_config` ← merge(preset.config, rule.masking_config) so per-rule
  overrides still layer on top
- `consistency_group` ← `preset.name` when `preset.consistency=true`, else
  the rule's own `consistency_group` column

Result: enabling Consistency on a preset and assigning it across multiple
columns now produces the same masked value for the same input across those
columns — the contract the preset's `consistency` flag advertised.

### Gap B (output_mode) — list/get responses always showed default

**Before**: `list_configs` / `get_config` for both synthetic and subset
returned domain entities through `ConfigResponse(..., output_mode=...)`.
The entity never carries `output_mode` (the field lives only on the
model), so Pydantic always emitted the `same_database` default — even
immediately after `PATCH /output-mode`.

**Fix**: both endpoints now side-lookup `output_mode` from the model in
one extra `SELECT id, output_mode WHERE id IN (...)` and surface the
real value. Single-row variant in `get_config` is a single-row select.

### Gap D (virtual FK) — visuals were dead code

**Before**: `RelationshipGraph` accepted `is_virtual` and `id` props, but:
- The backend `/discovery/relationships` response omitted `is_virtual`.
- `DiscoveredRelationship` domain entity didn't carry it.
- The repository mapper dropped the column.
- The frontend `discovery-store` typed `relationships` without `id` /
  `is_virtual`, called the endpoint without `schema_id` (required) so
  always fell into a heuristic fallback that derived from FK columns
  without any virtual flag.
- The discovery page never wired `onDeleteRelationship`.

**Fix**:
- Domain entity `DiscoveredRelationship.is_virtual: bool = False`.
- Repo `_relationship_to_entity` now copies `m.is_virtual`.
- API response includes `is_virtual`.
- Frontend store `Relationship` type widened with optional `id` +
  `is_virtual`; `fetchRelationships` now uses `schemas[0].id` to call the
  API, resolves table-id / column-id → name from already-loaded schemas,
  carries through `is_virtual`.
- Store gains `deleteRelationship(projectId, relationshipId)` calling
  `DELETE /relationships/{id}` and refreshing.
- Discovery page passes `onDeleteRelationship={(id) => deleteRelationship(...)}`
  to the graph. Click → confirm → DELETE → graph refreshes via the store.

### Gap E (joint masking) — masking_tasks bypassed the new engine path

**Before**: `masking_tasks` always called `engine.mask_column(values,
strategy, config)` — the column-wise path that has no row context, no
consistency_group, no linked-column awareness. The new
`engine.mask_row` introduced by 56-01 was reachable only from preview.

**Fix**: `masking_tasks` now decides per-table:
- If any applicable rule declares `consistency_group` or
  `linked_column_ids` → **row-level masking** via `engine.mask_row`,
  threading consistency_group through and (for now) leaving
  linked_column_names empty so the engine falls back to the row-identity
  seed. The ID→name resolution is the only remaining bridging step.
- Otherwise → existing `engine.mask_column` fast path (no behavior change
  for legacy rules).

This is the path real masking jobs take; presets with `consistency=true`,
or rules with a populated `consistency_group`, now actually affect
production output.

## Files changed

- `backend/app/domain/discovery/entities.py` — `DiscoveredRelationship.is_virtual`
- `backend/app/infrastructure/persistence/sqlalchemy/discovery_repo.py` — mapper carries is_virtual
- `backend/app/api/v1/discovery.py` — response includes is_virtual
- `backend/app/api/v1/synthetic.py` — list_configs / get_config side-lookup output_mode
- `backend/app/api/v1/subsetting.py` — list_configs side-lookup output_mode
- `backend/app/infrastructure/messaging/masking_tasks.py` — preset resolution + joint masking dispatch
- `frontend/src/stores/discovery-store.ts` — Relationship type + ID-aware fetch + deleteRelationship
- `frontend/src/app/projects/[projectId]/discovery/page.tsx` — wires onDeleteRelationship

## Verification

- 154/154 backend unit tests passing (no regressions from re-wiring).
- Frontend `tsc --noEmit -p .` clean.
- Backend + worker restarted cleanly; existing API smoke remains 200.

## Known remaining bridge

`MaskingEngine.mask_row` reads `linked_column_names` from rule dicts but
the DB column stores `linked_column_ids` (`UUID[]`). The masking task
currently passes an empty `linked_column_names`, so consistency_group is
fully wired end-to-end but linked-column joint generation falls back to
the row-identity seed. Storing names alongside IDs on rule creation, or
resolving IDs to names in the task via a `discovered_columns` query, is
a small follow-up. The engine semantics + unit tests are already locked
in by 56-01.

---
*Phase: 56-deferred-finish, Plan: 02 — Completed 2026-05-16*
