---
phase: 50-database-view
plan: 01
subsystem: api, frontend
tags: [database-view, columns, generators, inline-edit, status-pills]
requires:
  - phase: 48-shell-and-tokens
  - phase: 49-privacy-hub
provides:
  - GET /api/v1/projects/{id}/database — flat column list with status + generator
  - POST /api/v1/projects/{id}/database/columns/{column_id}/rule — upsert rule
  - DELETE /api/v1/projects/{id}/database/columns/{column_id}/rule — clear rule
  - /projects/[id]/database route — schema tree + filterable column table
  - "Database View" tab re-added to WorkspaceTabBar
duration: ~20min
completed: 2026-05-16
---

# Phase 50 Plan 01: Unified Database View

**Frontend tsc clean; backend reloaded; both new endpoints + new route return 200.**

## Highlights
- **Single working surface** for project columns. Read-only discovery output
  and editable masking-rule state are flattened into one paginated list.
  Each row carries `schema_name.table_name`, column name, data type, PII
  type + confidence, status pill, and an inline generator dropdown.
- **Status pills** use the new `--dw-pill-*` tokens:
  - Protected → green
  - Unprotected → amber
  - Not sensitive → muted
- **Inline upsert**: changing the generator dropdown calls the upsert
  endpoint; choosing "— No rule —" calls DELETE. Both endpoints share the
  default policy created by Privacy Hub.
- **Schema tree** in the left rail (220px) with per-table column counts and
  an "All tables" view. Selecting a table filters the right pane.
- **Filters**: free-text column / table / PII type search + status dropdown
  (all / protected / unprotected / not sensitive).
- **Database View tab re-added** to WorkspaceTabBar (was intentionally
  removed in 48-01 pending this route).

## API contract
```
GET    /api/v1/projects/{project_id}/database
       → { columns: ColumnRow[], generator_choices: string[] }

POST   /api/v1/projects/{project_id}/database/columns/{column_id}/rule
       body: { masking_type: string }
       → 200 { rule_id, masking_type, status: "created" | "updated" }

DELETE /api/v1/projects/{project_id}/database/columns/{column_id}/rule
       → 204
```

## Edge cases handled
- Column not in project → 404 from upsert.
- Invalid masking_type → 400 with allowed-list in detail.
- Project with no discovery yet → empty columns list, empty schema tree;
  page renders the empty-state message.
- DELETE with no existing rules → 204 idempotent (no-op).
- pii_confidence stored as `{score: ...}` dict — extracted defensively.

## Contract for Phase 51
- `GENERATOR_CHOICES` constant in `database_view.py` and
  `DEFAULT_GENERATOR_BY_PII` in `privacy_hub.py` will be replaced by the
  Generator Presets table in Phase 51. The frontend currently consumes
  `generator_choices` from the response — that array shape will remain
  stable; only its values may change.

## Manual verification
- [ ] Navigate to /projects/<id>/database — tab is visible and active.
- [ ] Schema tree appears on the left with per-table counts.
- [ ] Selecting a table filters the column table.
- [ ] Status pills render with the correct colours.
- [ ] Changing the dropdown creates/updates a rule and refreshes the row.
- [ ] Choosing "— No rule —" clears the rule and the status pill flips.

---
*Phase: 50-database-view, Plan: 01 — Completed 2026-05-16*
