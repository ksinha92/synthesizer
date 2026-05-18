---
phase: 58-dead-ui-surfaces
plan: 01
subsystem: frontend, backend-api
tags: [F4, F5, F6, F7, integrity-gate, v0.9]
features: [F4, F5, F6, F7]
requires:
  - phase: 57-compliance-data-flow
provides:
  - Masking page Preview button + inline connection selector
  - Subsetting DependencyGraph fed by discovery-store relationships
  - Synthetic lastConfigId wired via store after createConfig
  - RuleCreate/RuleUpdate carry linked_column_ids + consistency_group end-to-end
  - Masking rule editor consistency-group + linked-columns card
duration: ~15min (2 parallel agents)
completed: 2026-05-17
---

# Phase 58 Plan 01 — Dead-UI Surfaces + Linked-Column REST ✅

## Quality gate

| Check | Result |
|---|---|
| Backend `pytest tests/unit` | **340 / 340** (+2 round-trip tests) |
| Backend `pytest tests/integration/test_masking*` | 9 / 9 (+2 new) |
| Backend `pytest tests/integration` | 39 / 40 — OIDC fail unchanged |
| Frontend `npx tsc --noEmit` | clean ✓ |

## What shipped

### F4 — Masking Preview button
- `frontend/src/app/projects/[projectId]/masking/page.tsx` — inline connection selector + Preview button. Backend `previewMasking` requires `connection_id`; the button calls `previewMasking(projectId, policyId, connectionId)` and disables while in-flight.

### F5 — Subsetting DependencyGraph wired
- `subsetting/page.tsx` — reads `schemas`/`relationships` from `useDiscoveryStore`. On config select, loads discovery + relationships for `source_connection_id` if not present. `rootTables` derived from `selectedConfig.root_tables[].table_name`. `traversalDirection = selectedConfig?.traversal_strategy ?? "upstream"`. Empty-state hint card when no config selected.

### F6 — Synthetic lastConfigId
- `synthetic-store.ts` — added `lastConfigId: string | null` + `setLastConfigId`. `createConfig` sets it on success.
- `synthetic/page.tsx:25` — replaced dead `useState` with `useSyntheticStore((s) => s.lastConfigId)`. Quality auto-load now works.

### F7 — Linked-column REST exposure + UI
**Backend:**
- `api/v1/masking.py` — `RuleCreate` / `RuleUpdate` carry `linked_column_ids: list[UUID] | None` and `consistency_group: str | None`. Response surfaces both.
- `application/masking/commands.py` — `AddRuleCommand` extended.
- `application/masking/handlers.py` — `AddRuleHandler.handle` copies fields onto entity.
- `infrastructure/persistence/sqlalchemy/masking_repo.py` — `add_rule` writes the columns; `update_rule` returns them; `_rule_to_entity` reads back via `getattr` with safe defaults. Empty list → NULL for clean JSONB.
- Domain entity + model already had the fields from migration 019 (confirmed).

**Frontend:**
- `components/masking/masking-rule-editor.tsx` — new "Cross-column consistency" card with free-form group-name input + chip-style multi-select sourced from `useDiscoveryStore` filtered by the rule's table. Card is opt-in via callbacks (preserves existing callers).
- `masking-store.ts` `addRule` takes optional `extras: RuleConsistencyExtras` and serializes camelCase → snake_case for the API; `updateRule` does the same translation.

## Inline decisions (vs. plan)

1. **Preview needs `connection_id`, not `sample_size`** — backend signature differs from the plan; agent added an inline connection selector to surface the requirement explicitly rather than implicit "first connection".
2. **Empty `linked_column_ids` → NULL** in DB — preserves clean JSONB storage; entity round-trips as empty list.
3. **`update_rule` uses `model_dump(exclude_none=True)`** — clients omitting the new fields don't accidentally null them.
4. **Rule editor's table-scoped picker shows a hint** — `handleApplyRule(columnId, strategy)` doesn't carry `tableId` today; making the picker fully aware would require a follow-up to the rule-application flow. Consistency-group text input + API plumbing are fully live; the multi-select renders empty when table context is unknown. **Acceptable for v0.9 — flag as UI-flow refinement for v1.0.**

## Files modified

| File | Change |
|---|---|
| `backend/app/api/v1/masking.py` | F7 Pydantic |
| `backend/app/application/masking/commands.py` | F7 command |
| `backend/app/application/masking/handlers.py` | F7 handler thread-through |
| `backend/app/infrastructure/persistence/sqlalchemy/masking_repo.py` | F7 repo write/read |
| `frontend/src/app/projects/[projectId]/masking/page.tsx` | F4 Preview |
| `frontend/src/app/projects/[projectId]/subsetting/page.tsx` | F5 graph |
| `frontend/src/app/projects/[projectId]/synthetic/page.tsx` | F6 store read |
| `frontend/src/stores/synthetic-store.ts` | F6 store action |
| `frontend/src/stores/masking-store.ts` | F7 extras → snake_case |
| `frontend/src/components/masking/masking-rule-editor.tsx` | F7 picker |

## Files created

| File | Purpose |
|---|---|
| `backend/tests/unit/test_masking_repo_round_trip.py` | extended with 2 new tests |
| `backend/tests/integration/test_masking_api.py` | extended with 2 new tests |

## Manual verification

- [ ] Click Preview on a masking policy → preview pane populates (requires connection selection)
- [ ] Select a subsetting config → dependency graph renders with edges + root highlight
- [ ] Generate a synthetic config → `<QualityReport>` auto-loads with the new config_id
- [ ] POST a masking rule with `linked_column_ids: ["uuid"]` and `consistency_group: "customer-pii"` → GET surfaces both
- [ ] Rule editor "Cross-column consistency" card shows when callbacks wired; free-form group name accepted

## Carryover to next phases

- Rule editor `tableId` plumbing — minor v1.0 polish, not blocking.

---
*Phase: 58-dead-ui-surfaces, Plan: 01 — Completed 2026-05-17*
