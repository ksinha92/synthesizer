---
phase: 49-privacy-hub
plan: 01
subsystem: api, frontend
tags: [privacy-hub, dashboard, pii, recommendations, bulk-apply]
requires:
  - phase: 48-shell-and-tokens
provides:
  - GET /api/v1/projects/{id}/privacy-hub aggregate endpoint
  - POST /api/v1/projects/{id}/privacy-hub/apply-all idempotent bulk rule creator
  - DEFAULT_GENERATOR_BY_PII map (per-PII-type default generator suggestion)
  - <PrivacyHub> React component
  - Refactored project landing page (PrivacyHub + ActivityFeed)
duration: ~25min
completed: 2026-05-16
---

# Phase 49 Plan 01: Privacy Hub Dashboard

**Backend + frontend integrated. Frontend tsc clean; both endpoints respond.**

## Highlights
- **Backend aggregate** (`backend/app/api/v1/privacy_hub.py`):
  - Joins `connections → discovered_schemas → discovered_tables → discovered_columns`
    scoped to the project, counts `pii_type != "none"` columns as *sensitive*.
  - A separate query collects `column_id`s that already have at least one
    masking rule in any of the project's policies → those columns are *protected*.
  - Returns counters + a `recommendations` list grouped by PII type with
    `unprotected_columns` count and a `recommended_generator` per group.
- **Bulk apply** is idempotent: re-running with the same PII types finds no
  unprotected targets, returns `rules_created: 0`. Creates (or reuses) a
  "Default" `masking_policy` row per project as the home for auto-generated rules.
- **Default-generator map** lives in code, not the DB — easy to evolve before a
  full Generator Presets feature ships in Phase 51. SSN / credit_card /
  financial_account / medical_record → `hash`; everything human-readable →
  `faker_replace`; unknown → `redact`.
- **Frontend `<PrivacyHub>`**: three counter cards (sensitive / protected /
  unprotected) with brand / success / warning accent colors from the new `--dw-*`
  tokens, a recommendations table with per-row Apply and a hero "Apply all"
  button using the same gradient as the workspace Generate Data CTA.
- **Project landing page** simplified: project header → `<PrivacyHub>` →
  ActivityFeed card. The old stat-card / count-fetching loop is gone — counts
  now come from the aggregator instead of N parallel requests.

## API contract
```
GET  /api/v1/projects/{project_id}/privacy-hub
  → { sensitive_count, protected_count, unprotected_count, recommendations[] }

POST /api/v1/projects/{project_id}/privacy-hub/apply-all
  body: { pii_types: [string] }
  → 201 { rules_created, policy_id }
```

## Edge cases handled
- Project with no connections / discovery → all counts 0, recommendations []
  → UI shows the "Nothing left to protect" empty state.
- Connection deleted via CASCADE from migration 015 → its discovered_columns
  cascade with it; counts reflect current state immediately.
- Rule already exists for a column → not counted as a new creation
  (idempotency check via `_project_protected_column_ids`).
- Bulk apply with `pii_types: []` → 400 with clear error message.

## Manual verification
- [ ] On a project with discovered PII, three counters render with the right totals.
- [ ] Recommendations list shows each PII type with its unprotected count.
- [ ] "Apply" creates rules; counters refresh; the same type drops to 0.
- [ ] "Apply all" runs across remaining types; idempotent on re-click.

## Next plans in v0.8
- Phase 50: Unified Database View.
- Phase 51: Generator Presets (table + drawer; replaces the in-code default map).
- Phase 52: Sensitivity Rules admin.
- Phase 53: Recommended Generators + linked-column consistency.
- Phase 54: Destination connections + virtual FKs + schema-changes diff.
- Phase 55: Final unify + quality gate + v0.8 ship.

---
*Phase: 49-privacy-hub, Plan: 01 — Completed 2026-05-16*
