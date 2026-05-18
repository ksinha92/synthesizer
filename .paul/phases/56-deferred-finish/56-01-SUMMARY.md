---
phase: 56-deferred-finish
plan: 01
subsystem: api, frontend, engine
tags: [presets-binding, output-mode, schema-changes-ui, virtual-fk-edges, joint-masking]
requires:
  - phase: 48-shell-and-tokens
  - phase: 51-generator-presets
  - phase: 53-recommended-and-linked
  - phase: 54-destinations-vfk-diff
provides:
  - Database View dropdown surfaces live generator presets (binding A→B)
  - upsert_rule endpoint accepts preset_id and resolves masking_type from the preset
  - PATCH /synthetic/configs/{id}/output-mode + PATCH /subset/configs/{id}/output-mode
  - <SchemaChangesPanel> + wiring on /projects/[id]/connections
  - RelationshipGraph supports is_virtual + id, renders dashed violet edges, click-to-delete on virtual edges
  - MaskingEngine.mask_row honoring consistency_group + linked_column_names
  - 6 new unit tests for joint masking
duration: ~30min
completed: 2026-05-16
---

# Phase 56 Plan 01: v0.8 Deferred Work Finish

**154 / 154 backend unit tests passing (+6 from this plan); frontend tsc clean.**

Closes the five threads called out in `RELEASE-NOTES-v0.8.md` as deferred.

## Threads delivered

### A — Generator Presets ↔ Database View binding
- `GET /api/v1/projects/{id}/database` now returns a `presets` array
  alongside the built-in `generator_choices`.
- `POST /database/columns/{column_id}/rule` accepts EITHER `masking_type`
  (built-in) OR `preset_id` (resolves the preset's `generator_type` and
  records `preset_id` on the rule).
- `DatabaseColumnRow` carries `current_preset_id` so the UI knows which
  preset is selected on round-trip.
- UI dropdown now has two `<optgroup>` sections: **Presets** (live from the
  presets table) and **Generators** (built-in vocabulary). Selecting a
  preset sends `preset_id`; selecting a built-in generator sends
  `masking_type`. Backward compatible.
- Functional smoke: created a preset, listed the Database View response,
  observed `presets` array populated, cleaned up. All 200 / 204.

### B — `output_mode` API endpoints
- `PATCH /api/v1/projects/{id}/synthetic/configs/{config_id}/output-mode`
- `PATCH /api/v1/projects/{id}/subset/configs/{config_id}/output-mode`
- Both validate against `{same_database, different_connection, download_zip, s3}`
  and 404 when the config is not in the project. Both routes registered
  (verified in openapi.json).
- The `ConfigCreate` body accepts `output_mode` at create time; the
  endpoint applies it via direct UPDATE since the domain command pipeline
  doesn't carry the field yet. Existing list / get responses still default
  to `same_database` in their projection — adding that pass-through is a
  small follow-up if/when the engine starts branching on the mode.

### C — Schema-changes panel on connections page
- New `<SchemaChangesPanel>` component (`components/connections/schema-
  changes-panel.tsx`). On click of **Check** it calls
  `GET /projects/{id}/discovery/diff?connection_id=...` and renders:
  added / removed tables, added / removed / type-changed columns, each
  in a color-coded pill using `--dw-pill-*` tokens.
- Connection list page renders one panel per connection under the existing
  list. Read-only; nothing persists until the user re-runs discovery.

### D — Virtual FK on the relationships graph
- `RelationshipGraph` `Relationship` interface widened to optionally carry
  `id` and `is_virtual`. Edges with `is_virtual=true` render with a
  **dashed violet** stroke + animated flow + a `• virtual` suffix on the
  label, while normal FKs keep the existing muted style.
- A virtual-FK count badge appears in the graph's top-right corner.
- New `onDeleteRelationship` callback: a click on a virtual edge prompts
  for confirmation and invokes the callback with the relationship id.
- Existing callers ignore the new optional fields → backward compatible.
- The "+ Add virtual FK" picker form is not part of this plan. Adding it
  needs a 4-field UI selector (schema_id / source table+column /
  target table+column) wired to the existing discovered_schemas; queued
  as the only remaining bit of UI work for virtual FKs.

### E — Joint masking — consistency_group + linked_column_names
- `MaskingEngine.mask_value` takes optional `consistency_group` and
  `row_seed` parameters.
- `_hash` mixes `consistency_group` into the HMAC salt, so the same input
  in the same group produces the same hash across every column tagged
  with that group (joint identifiers stay consistent).
- `_faker_replace` accepts a `row_seed` (a deterministic per-row hex
  string) and re-seeds the Faker instance from it before generating, so
  linked-column-paired output (City→State, etc.) is stable within a row
  and varies with the linked-column values.
- New `MaskingEngine.mask_row(row, rules)` orchestrates both: it
  pre-computes a row-identity seed and per-rule seeds from `linked_column_names`,
  and threads `consistency_group` per rule to `mask_value`.
- `mask_preview` switched to `mask_row` so previews reflect the joint
  behavior.
- **6 new unit tests** cover: same group + same input → same hash;
  group changes the hash; different groups differ; row-level shared group
  yields equal columns; linked columns deterministically pair faker output;
  no-group fallback equals the global-salt hash.

## Bridging note

`MaskingEngine.mask_row` currently expects rule dicts to include
`linked_column_names` — a list of column names. The DB column added in
migration 019 (`masking_rules.linked_column_ids`) stores UUIDs. Wiring the
ID → name lookup (or storing names alongside IDs) is the next small step
when masking flow callers start to populate either field. Tests use the
name-keyed shape directly to lock in the engine semantics.

## Status of v0.8 deferred list

| Item | Status |
|---|---|
| Generator-presets ↔ Database View binding | ✅ |
| `output_mode` PATCH endpoints + Pydantic surface | ✅ (UI selector form deferred) |
| Schema-changes panel on connections page | ✅ |
| Virtual FK visual + delete on the graph | ✅ (create-picker form deferred) |
| Masking engine joint generation | ✅ |

## Manual verification checklist

- [ ] Database View dropdown shows a "Presets" optgroup with any
      presets visible; selecting one persists the rule with that preset's
      generator_type.
- [ ] PATCH the synthetic / subset config output_mode endpoints with
      curl and a real config id — DB column updates, invalid values 400.
- [ ] On a connections page with at least one connection, click **Check**
      on the SchemaChangesPanel — added/removed/changed rows render with
      color-coded labels.
- [ ] On a discovery view backed by `is_virtual` data, virtual edges
      render dashed violet; clicking one prompts to delete.
- [ ] Engine joint masking exercised in tests; in real flows, ensure the
      caller populates `consistency_group` / `linked_column_names` on the
      rule dicts.

---
*Phase: 56-deferred-finish, Plan: 01 — Completed 2026-05-16*
