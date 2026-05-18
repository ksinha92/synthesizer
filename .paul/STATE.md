# Project State

## Project Reference

See: .paul/PROJECT.md

**Core value:** AI-powered TDM platform replacing Delphix for Ameritas.
**Current focus:** v0.9 Integrity Gate — ✅ SHIPPED 2026-05-17

## Current Position

Milestone: v0.9 Integrity Gate — ✅ SHIPPED 2026-05-17
All 5 phases (57–61) complete. Migrations 022, 024–029 applied (head 029).
20 features (F1–F20) closed across Compliance/Privacy Hub data-flow, Dead-UI surfaces, Async reliability, Security & trust, and Stability/housekeeping.

Progress:
- v0.8 UX Refactor: [██████████] ✅ 100% (shipped 2026-05-16)
- Phase 56 deferred-work close-out: [██████████] ✅ shipped 2026-05-16
- v0.9 Integrity Gate: [██████████] ✅ 100% (5 of 5 phases shipped 2026-05-17)

## Loop Position

```
PLAN ──▶ APPLY ──▶ UNIFY
  ✓        ✓        ✓     [v0.9 closed. See .paul/phases/57-* through 61-* SUMMARYs]
```

## Quality gate (v0.9 close — 2026-05-17)

- Backend `pytest tests/unit`: **424 / 424** ✓ (+92 from 332 baseline; +27 from 397 v0.8.1)
- Backend `pytest tests/integration`: 41 / 42 (pre-existing OIDC env-config fail unchanged)
- Frontend `tsc --noEmit`: clean ✓
- Frontend `/projects` SSR regression: **FIXED** (Phase 61 F17)
- Alembic head: **029**
- Runtime probes: 12/12 backend endpoints 200, 12/12 frontend page-loads 200

## v0.9 deferred to v1.0
- Ephemeral `masking_policy_id` column + UI selector (data_copy already supports it).
- celery-beat schedule wiring for `run_ephemeral_expire_sweep_task` + `redrive_pending_webhook_deliveries`.
- Redis-backed rate-limiter for multi-worker deploys.
- Rule-editor `tableId` plumbing so linked-column picker is fully aware (Phase 58 caveat).
- Connector contract pagination (`get_sample_data` → pageable selects).

## v0.9 feature roster (20 features, 5 phases)

See `.paul/MILESTONE-CONTEXT.md` snapshot — file deleted after creation; canonical record now lives in ROADMAP.md and per-phase CONTEXT.md files. Open questions captured in ROADMAP.md per-phase sections.

## Defaults adopted for v0.8 open questions
1. Start timing: NOW (v0.7 shipped).
2. Project vs Workspace: kept "Project".
3. Generate Data CTA: split-button covering all 5 workspace verbs.
4. Theme: System default for content; global top bar always dark.

## Prior Milestones
- v0.1 MVP: 10 phases, 48 audit fixes. Complete.
- v0.2 Advanced: 6 phases, 13 audit fixes. Complete.
- v0.3 Enterprise: 8 phases, 14 audit fixes. Complete.
- v0.4 Frontend Completion: 8 phases, 8 plans. Complete.
- v0.5 UI Fixes + Production Readiness: 5 phases, 5 plans. Complete.
- v0.6 Full-Stack Wiring + Gap Closure: 5 phases, 5 plans. Complete.

## Session Continuity

All 6 milestones complete. 42 phases across 6 milestones delivered.

v0.7 Phase 43 complete:
- 43-01: FileSchemaDefinition domain model (6 value objects, 3 enums) + COBOL copybook parser
- 43-02: ExcelDictionaryParser + FileSchemaRepository + FileSchemaModel + 5 API endpoints

v0.7 complete (autonomous loop 2026-05-16):

- Phase 43: FileSchemaDefinition + COBOL copybook parser + Excel dictionary parser + 5 API endpoints
- Phase 44 (3 plans):
  - 44-01: BaseFileWriter ABC + write_atomic + CSVWriter + FixedWidthWriter (+21 tests)
  - 44-02: EBCDIC codec + COBOL encoders + VSAMWriter fixed/variable (+33 tests)
  - 44-03: ColumnarWriter (Parquet/ORC) + WriterRegistry + GET /api/v1/file-formats (+15 tests)
- Phase 45: sample_file_parser (5 formats) + DistributionProfiler + FakerEngine profile-guided (+19 tests)
- Phase 46: FileSetOrchestrator + zip_bundler + run_file_set_generation_task + download endpoint (+6 tests)
- Phase 47: POST /file-sets/generate + useFileOutputStore + FileOutputPanel + page tabs

Total: 148/148 backend unit tests; pyarrow>=18.0.0 added to deps.

Next action: when ready, kick off milestone v0.8 (UX Refactor) — Phase 48 CONTEXT.md already drafted.

---

## Proposed Milestone v0.8 — UX Refactor (DEFERRED until v0.7 ships)

Phase 48 discuss-output written (`.paul/phases/48-shell-and-tokens/CONTEXT.md`).
Roadmap updated with proposed phases 48–55. Per user direction 2026-05-16,
v0.8 will NOT start until v0.7 (phases 44–47) is complete.

Open Question #1 (start timing) resolved: **finish v0.7 first.**
Open Questions #2–#4 (Project vs Workspace label, Generate Data CTA scope,
theme/global-bar relationship) remain to be answered before `/paul:plan`
for Phase 48 — at the time v0.8 actually starts.

Supporting docs (already written, ready when v0.8 kicks off):
- `docs/UX-DESIGN-GUIDE.md`
- `docs/UX-FEATURE-MAPPING.md`
- `.paul/phases/48-shell-and-tokens/CONTEXT.md`

## Immediate next action

Run `/paul:apply` against `.paul/phases/44-file-writers/44-01-PLAN.md`
(4 tasks: BaseFileWriter ABC + write_atomic, CSVWriter, FixedWidthWriter,
round-trip unit tests). Plan adopts the recommended defaults from the
discuss CONTEXT.md for all five open questions:

1. EBCDIC library → stdlib (no impact in 44-01; relevant in 44-02)
2. Arrow decimal mapping → decimal128 (relevant in 44-03)
3. CSV BOM → default OFF, configurable via `CSVWriter(write_bom=True)`
4. VSAM blocking → RDW only (relevant in 44-02)
5. Writer methods → sync (Celery task is the async layer)

If you want to override any of these before APPLY, edit the PLAN and STATE.

---
