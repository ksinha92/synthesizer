# Roadmap: DataWrangler

## Overview

AI-Powered Test Data Management Platform that replaces Delphix for Ameritas. Started as DDD foundation with connectors and discovery, expanded through synthetic engines, masking, subsetting, workflow builder, enterprise compliance, full frontend completion, and production wiring. Now extending into file-based synthetic data generation for mainframe and batch processing workflows.

## Milestones

| Version | Name | Phases | Status | Completed |
|---------|------|--------|--------|-----------|
| v0.1 | MVP Release | 1-10 | ✅ Shipped | 2026-03-29 |
| v0.2 | Advanced Features | 11-16 | ✅ Shipped | 2026-03-29 |
| v0.3 | Enterprise | 17-24 | ✅ Shipped | 2026-03-29 |
| v0.4 | Frontend Completion | 25-32 | ✅ Shipped | 2026-03-31 |
| v0.5 | UI Fixes + Production Readiness | 33-37 | ✅ Shipped | 2026-04-01 |
| v0.6 | Full-Stack Wiring + Gap Closure | 38-42 | ✅ Shipped | 2026-04-01 |
| v0.7 | File-Based Synthetic Data Generation | 43-47 | ✅ Shipped | 2026-05-16 |
| v0.8 | UX Refactor | 48-55 | ✅ Shipped | 2026-05-16 |
| v0.9 | Integrity Gate | 57-61 | ✅ Shipped | 2026-05-17 |

## ✅ Milestone shipped: v0.9 Integrity Gate

**Goal:** Close the integration-seam gaps surfaced by the 2026-05-17 swarm evaluation (`docs/FEATURE-EVALUATION.md`). No new features — earn back trust before v1.0. 6 of 12 features rated 🔴 today; v0.9 closes all six.
**Prerequisite:** v0.8 complete (shipped 2026-05-16) + Phase 56 deferred-work close-out (shipped 2026-05-16).
**Status:** Phase 57 ready to plan.
**References:** `docs/FEATURE-EVALUATION.md`, `.paul/phases/57-compliance-data-flow/` … `.paul/phases/61-stability-housekeeping/`.

### Phase 57: Compliance + Privacy Hub Data-Flow
**Goal:** Fix the "looks done, isn't" data-flow gaps. Compliance reports stop shipping with empty PII/rule lists; Privacy Hub `apply-all` actually enqueues masking; compliance generation moves off the request thread.
**Features:** F1 (compliance handler wired to discovery_repo + masking_repo), F2 (compliance_tasks.py Celery + 202 + job_id + narrative refresh), F3 (privacy_hub apply-all enqueues run_masking_task).
**Open questions:** Re-generate archived compliance reports after F1 or label them "pre-v0.9 placeholder"?
**Plans:** TBD (defined during /paul:plan).

### Phase 58: Dead-UI Surfaces + Linked-Column REST Exposure
**Goal:** Reach the masking preview, the subsetting dependency graph, and the synthetic quality auto-load — all rendered today but never invoked. Expose linked-column joint-generation through REST (engine + worker shipped in Phase 53; API silently strips the fields).
**Features:** F4 (masking preview button + wire), F5 (subsetting DependencyGraph wired to discovery-store), F6 (synthetic lastConfigId wired or removed), F7 (linked_column_ids + consistency_group on RuleCreate/RuleUpdate + UI picker).
**Plans:** TBD (defined during /paul:plan).

### Phase 59: Async + Observability Reliability
**Goal:** Make the job/workflow/observability plane actually work — DLQ populated, cancel revokes, checkpoint resumes, scheduling is real, SSE is push not poll.
**Features:** F8 (DLQ via celery task_failure signal + retry payload), F9 (celery_task_id populated), F10 (JobType enum extended), F11 (workflow reliability — checkpoint resume + NODE_TIMEOUT + fail-fast + TOCTOU fix + created_by), F12 (cron scheduling — ship or delete), F13 (SSE → Redis pub/sub).
**Open questions:** Cron scheduling direction — ship celery-beat or delete `schedule` field? Check production DB for existing cron values before committing.
**Plans:** TBD (defined during /paul:plan).

### Phase 60: Security & Trust
**Goal:** Make the security surfaces match the documentation. Webhook HMAC verifiable, RBAC enforced across every router, preflight rate-limited.
**Features:** F14 (webhook HMAC keyed on raw secret + webhook_deliveries table + X-Webhook-Timestamp + signal-handler dispatch), F15 (RBAC propagation + project-ownership consistency + dev-bypass audit), F16 (connection preflight rate-limit).
**Open questions:** RBAC default for existing users (editor vs viewer)? Webhook secret migration strategy (force rotation vs deprecation window)?
**Plans:** TBD (defined during /paul:plan).

### Phase 61: Stability + Housekeeping
**Goal:** Fix the SSR regression on `/projects`, ship the Ephemeral data-copy controller, split oversized files, pin tooling. The biggest single piece of work in the milestone is the Ephemeral provisioner.
**Features:** F17 (SSR useContext null on /projects), F18 (Ephemeral data-copy controller — anchor; pending → provisioning → ready → expired; TTL sweep as background task; extend-TTL endpoint), F19 (split synthetic.py 1034 LOC + extract ephemeral/page.tsx 542 LOC), F20 (pin pytest/pytest-asyncio + resolve pnpm/npm doc drift).
**Open questions:** Ephemeral deployment shape — Docker-Compose temp containers vs. snapshot-clone vs. logical-replication? Largest open architecture decision; warrants a discuss-phase output before 61-01-PLAN.md.
**Plans:** TBD (defined during /paul:plan).

## ✅ Milestone shipped: v0.8 UX Refactor

**Goal:** Align the visual + interaction system with the enterprise-TDM reference as DataWrangler's default chrome and key workflow surfaces while preserving every feature shipped through v0.7. Adds new capabilities surfaced by the reference UX: Privacy Hub dashboard, unified Database View, Generator Presets, Sensitivity Rules admin, Recommended Generators bulk apply, linked-column consistency, destination connections, virtual FKs, schema-changes diff.
**Prerequisite:** v0.7 complete (open question #1 — see Phase 48 CONTEXT.md).
**Status:** Phase 48 discuss-output written; awaiting decision on 4 open questions before `/paul:plan`.
**References:** `docs/UX-DESIGN-GUIDE.md`, `docs/UX-FEATURE-MAPPING.md`, `.paul/phases/48-shell-and-tokens/CONTEXT.md`.

### Phase 48: Shell + Design Tokens
**Goal:** Two-bar app shell (global + workspace tabs) replacing the sidebar, Tailwind theme tokens for the UX palette/typography/density, right-side ContextDrawer standardization, Generate Data ▾ primary CTA.
**Plans:** none yet — discuss output in CONTEXT.md.

### Phase 49: Privacy Hub Dashboard ✅
**Goal:** Goal-driven project landing page — unprotected-columns counter, recommended-generators panel, "Apply all" bulk action, recent activity.
**Plans:**
- [x] 49-01: GET /privacy-hub aggregator + POST /privacy-hub/apply-all + <PrivacyHub> UI + landing-page rewrite

### Phase 50: Database View — Unified Column Working Surface ✅
**Goal:** Merge read-only discovery results with editable masking-rule view into a single Database View page with status pills and inline generator picker.
**Plans:**
- [x] 50-01: GET/POST/DELETE /database endpoints + /projects/[id]/database page + tab re-add

### Phase 51: Generator Presets ✅
**Goal:** Reusable, named generator configurations. Migration 017 adds `generator_presets` and `masking_rules.preset_id`. Presets page with side-drawer edit.
**Plans:**
- [x] 51-01: Migration 017 + model + CRUD + /generator-presets page + nav link

### Phase 52: Sensitivity Rules Admin ✅
**Goal:** User-defined detectors (regex / column-name / value-pattern). Migration 018 adds `sensitivity_rules`. Discovery-pipeline integration deferred to 53-01.
**Plans:**
- [x] 52-01: Migration 018 + model + CRUD + /sensitivity-rules page + nav link

### Phase 53: Recommended Generators + Linked Columns ✅
**Goal:** One-click bulk-apply across detected PII types (delivered in 49). Linked-column schema + sensitivity-rule wire-up to PII pipeline. Migration 019 adds `linked_column_ids` + `consistency_group`. Masking engine joint-generation update deferred.
**Plans:**
- [x] 53-01: Migration 019 + custom_rules helper + PIIDetectionService Layer 0 + discovery task wire-up

### Phase 54: Destination Connections + Virtual FKs + Schema Changes ✅
**Goal:** Promote `target_connection_id` to first-class destination concept with output modes. Virtual FK assertion API. Schema-changes diff endpoint. UI surfacing of all three queued for Phase 55 polish pass.
**Plans:**
- [x] 54-01: Migration 020 + output_mode columns + virtual FK CRUD + /discovery/diff endpoint

### Phase 55: Quality Gate + v0.8 Ship ✅
**Goal:** Final test/lint/typecheck sweep, ruff auto-fix pass, release notes, milestone close.
**Plans:**
- [x] 55-01: pytest 148/148 + tsc clean + 39 ruff auto-fixes + docs/RELEASE-NOTES-v0.8.md

## 🚧 Active Milestone: v0.7 File-Based Synthetic Data Generation

**Goal:** Extend synthetic data generation to file outputs — CSV, fixed-width flat files, VSAM (fixed/variable, EBCDIC/COMP-3), Parquet/ORC. Schema input via COBOL copybook, Excel data dictionary, manual builder, or existing discovery metadata. Sample file upload for distribution-guided generation. Multi-file generation with cross-file referential integrity and mixed formats. Zip download delivery.
**Prerequisite:** v0.6 complete
**Status:** Phase 44 planning
**Progress:** [██░░░░░░░░] 20% (1 of 5 phases)

### Phase 43: Schema Parsers & Internal Model

**Goal:** Unified FileSchemaDefinition domain model and all schema input parsers
**Depends on:** Nothing (first phase of milestone)
**Research:** Likely (COBOL copybook dialect variations, PIC clause edge cases)

**Scope:**
- FileSchemaDefinition value objects (fields, format, encoding, record length, COMP types)
- FileSetDefinition with cross-file FK declarations
- COBOL copybook parser (PIC clauses, COMP-3, REDEFINES, OCCURS) — custom + library fallback
- Excel data dictionary parser (.xlsx with field definitions, header auto-detection)
- Upload API endpoints for copybook, dictionary, manual entry, and discovery-based schema creation

**Plans:**
- [x] 43-01: FileSchemaDefinition domain model + copybook parser
- [x] 43-02: Excel dictionary parser + upload API endpoints

### Phase 44: File Writers

**Goal:** Writer implementations for all five output formats
**Depends on:** Phase 43 (FileSchemaDefinition model)
**Research:** Likely (EBCDIC encoding, COMP-3 packed decimal, VSAM record structure)

**Scope:**
- BaseFileWriter ABC with format-specific implementations
- CSVWriter (configurable delimiter, quoting, encoding)
- FixedWidthWriter (ASCII, position-based, pad characters)
- VSAMWriter fixed + variable (EBCDIC CP037/CP1140, COMP-3, COMP binary, RDW prefix)
- ColumnarWriter (Parquet/ORC via pyarrow, configurable compression)
- Writer registry with format-to-writer mapping

**Plans:**
- [x] 44-01: BaseFileWriter + CSVWriter + FixedWidthWriter
- [x] 44-02: VSAMWriter (EBCDIC, COMP-3, fixed + variable)
- [x] 44-03: ColumnarWriter + writer registry

### Phase 45: Sample File Parsing & Profiling

**Goal:** Parse sample files in native format, profile distributions for guided generation
**Depends on:** Phase 44 (writers define format expectations)
**Research:** Likely (distribution fitting, pattern detection algorithms)

**Scope:**
- Sample file parsers matching target format (CSV, fixed-width, VSAM binary decode, Parquet/ORC)
- Distribution profiler — numeric fitting, categorical frequencies, string patterns, null rates, correlations
- Profile-guided Faker integration — constrain generation with learned distributions and patterns

**Plans:**
- [ ] 45-01: Sample file parsers (all formats) + distribution profiler
- [ ] 45-02: Profile-guided Faker integration

### Phase 46: Multi-File Generation & Orchestration

**Goal:** Generate multiple related files with cross-file FK integrity in one run
**Depends on:** Phase 45 (profiling feeds into generation)
**Research:** Unlikely (reuses existing topological sort from FakerEngine)

**Scope:**
- FileSetOrchestrator — topological sort across file schemas, cross-file FK integrity
- Mixed-format generation (each file can be different format in one run)
- Zip bundler with user-defined or auto-generated filenames + manifest
- Celery task extension for file generation jobs
- Download endpoint for streaming zip files

**Plans:**
- [ ] 46-01: FileSetOrchestrator + zip bundler + Celery task + download endpoint

### Phase 47: Frontend — File Output Mode

**Goal:** Full UI for file-based synthetic data generation workflow
**Depends on:** Phase 46 (backend APIs must exist)
**Research:** Unlikely (extends existing synthetic page patterns)

**Scope:**
- File Output tab on synthetic page
- Schema source selector (copybook upload, Excel dictionary, manual column builder, discovery pull)
- File set builder — multiple files with per-file format, row count, FK relationship editor
- Sample upload with profiling results display
- Generation panel with progress tracking and zip download
- Zustand store extension for file schemas, file sets, sample profiles

**Plans:**
- [ ] 47-01: Schema source selector + file set builder
- [ ] 47-02: Sample upload + generation panel + download + store

## ✅ Completed Milestones

<details>
<summary>v0.6 Full-Stack Wiring + Gap Closure (Phases 38-42) — Shipped 2026-04-01</summary>

5 phases, 5 plans. Backend API gaps, orphaned features UI, workflow + subsetting completion, data quality + monitoring, UX edge cases + polish.

### Phase 38: Backend API Gaps (P0)
**Goal:** Build missing RBAC member management endpoints, fix pii_confidence type mismatch, add workflow detail/execution/subset listing/masking rule CRUD endpoints
**Plans:** 1 complete
- [x] 38-01: Backend API gaps

### Phase 39: Orphaned Features UI
**Goal:** Schema introspection UI, webhook management, encryption key rotation, dead letter queue viewer
**Plans:** 1 complete
- [x] 39-01: Orphaned features UI

### Phase 40: Workflow + Subsetting Completion
**Goal:** Workflow scheduling UI with cron editor, execution history, subset config listing, masking rule edit/delete, connection delete
**Plans:** 1 complete
- [x] 40-01: Workflow + subsetting completion

### Phase 41: Data Quality + Monitoring
**Goal:** Real synthetic quality comparison, health dashboard, compliance download auth fix, profile editing
**Plans:** 1 complete
- [x] 41-01: Data quality + monitoring

### Phase 42: UX Edge Cases + Polish
**Goal:** SSE reconnection, NLP timeout UX, notification persistence, user-scoped onboarding, contract test validation
**Plans:** 1 complete
- [x] 42-01: UX edge cases + polish

</details>

<details>
<summary>v0.5 UI Fixes + Production Readiness (Phases 33-37) — Shipped 2026-04-01</summary>

5 phases, 5 plans. Critical UI blockers, dashboard stats wiring, masking/synthetic/discovery completion, error handling polish, testing + deployment docs.

</details>

<details>
<summary>v0.4 Frontend Completion (Phases 25-32) — Shipped 2026-03-31</summary>

8 phases, 8 plans. Quality visualization (Recharts), relationship + subsetting graphs (ReactFlow), notification center, onboarding wizard, PII heatmap, job Gantt, form validation (react-hook-form + zod), Ant Design Tables, skeleton loading, WCAG 2.1 AA accessibility, mobile responsiveness, Playwright E2E.

</details>

<details>
<summary>v0.3 Enterprise (Phases 17-24) — Shipped 2026-03-29</summary>

8 phases, 8 plans, 14 enterprise audit fixes. Compliance reports (HIPAA/GDPR/CCPA), RBAC + audit trail, CLI + webhooks, ReactFlow canvas, AI assistant, Fernet encryption, production hardening.

</details>

<details>
<summary>v0.2 Advanced Features (Phases 11-16) — Shipped 2026-03-29</summary>

6 phases, 6 plans, 13 enterprise audit fixes. Statistical + LLM synthetic engines, masking (7 strategies + FPE), subsetting (FK graph), workflow builder (DAG), advanced frontend pages.

</details>

<details>
<summary>v0.1 MVP Release (Phases 1-10) — Shipped 2026-03-29</summary>

10 phases, 11 plans, 48 enterprise audit fixes. DDD foundation, auth, 4 connectors, discovery, PII detection, Faker engine, LLM provider, job system. Frontend: shadcn/Tailwind hybrid, 7 pages, SSE progress, dark/light/system theme.

</details>

---
*Last updated: 2026-05-17*
