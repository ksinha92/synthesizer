# Phase 58 Context — Dead-UI Surfaces + Linked-Column REST Exposure

> Discuss-phase output for v0.9 Integrity Gate. Auto-mode 2026-05-17.

## Vision

Reach the UI surfaces that v0.8 shipped-but-never-wired: the masking preview pane, the subsetting dependency graph, and the synthetic quality auto-load. Plus expose linked-column joint generation (engine + worker already in production since Phase 53/migration 019) through REST so clients can actually use it.

## Goals

1. **F4 — Masking Preview button.** Add a Preview action on the masking policies page that calls `useMaskingStore.previewMasking(...)`. Today the page renders `<MaskingPreview data={previewData}/>` but no UI ever triggers `previewMasking()` — the pane is permanently empty.
2. **F5 — Subsetting DependencyGraph wired.** Today `subsetting/page.tsx:82-84` passes `relationships={[]}` and `rootTables={[]}` so the graph renders disconnected nodes. Fetch real relationships from `discovery-store`; derive `rootTables` from the selected config; mirror `traversalDirection` from `config.traversal_strategy`.
3. **F6 — Synthetic `lastConfigId` wired.** `synthetic/page.tsx:25` declares `const [lastConfigId] = useState(null)` without a setter — `<QualityReport configId={lastConfigId}/>` always receives null. Wire it via the store after `createConfig`.
4. **F7 — Linked-column REST exposure.** Add `linked_column_ids: list[uuid.UUID]` and `consistency_group: str | None` to `RuleCreate`/`RuleUpdate` Pydantic in `api/v1/masking.py`. Engine + worker + DB schema already consume these (migration 019). UI: consistency-group picker on the masking rule editor.

## Constraints

- No new migrations (DB schema already supports linked columns).
- No backend behavior changes outside the masking API surface (engine + worker unchanged).
- Preserve existing tests; add new tests for F4/F5 wiring and F7 round-trip.
- Keep dead-state risk in mind: `lastConfigId` becomes derived state — don't reintroduce stale-closure bugs.

## Plans

| Plan | Scope |
| --- | --- |
| **58-01** | All 4 features in one plan — separable in code but conceptually all "v0.8 ships features that don't reach the UI". |

---
*Created: 2026-05-17*
