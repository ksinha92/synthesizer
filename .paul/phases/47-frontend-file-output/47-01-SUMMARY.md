---
phase: 47-frontend-file-output
plan: 01
subsystem: api, frontend
tags: [file-output, multi-file, zustand, ui, download]
requires:
  - phase: 44-file-writers
  - phase: 45-sample-profiling
  - phase: 46-orchestration
provides:
  - POST /projects/{id}/synthetic/file-sets/generate endpoint
  - useFileOutputStore Zustand store (schemas, file-set builder, job polling)
  - FileOutputPanel React component
  - Synthetic page "Database / File output" mode toggle
duration: ~25min
completed: 2026-05-16
---

# Phase 47 Plan 01: File Output UI

**148/148 backend unit tests green; frontend tsc clean.**

## Highlights
- **Backend**: new `POST /projects/{id}/synthetic/file-sets/generate` validates
  the FileSetDefinition payload, creates a JobModel row, dispatches
  `run_file_set_generation_task.delay(file_set, project_id, job_id)`, and
  returns the job_id. Celery task updated to honor `row_counts` from the
  inbound dict.
- **Frontend store** (`useFileOutputStore`): fetches the project's file schemas,
  tracks selected schemas + per-schema format/row count, declarable cross-file
  FKs, current job, polling, download URL helper.
- **FileOutputPanel** component: selectable schema table, format dropdown
  (CSV / Fixed-width / VSAM Fixed / VSAM Variable / Parquet / ORC), row count
  input, cross-file FK editor, Generate button, status-aware UI with 2-second
  poll loop and a "Download zip" affordance when complete.
- **Synthetic page tabs**: Database | File output toggle preserves existing
  flows; new mode renders the panel without touching the LLM/Faker paths.

## v0.7 milestone closure
- Phase 43 ✅ — Schema parsers + internal model
- Phase 44 ✅ — File writers (CSV/Fixed/VSAM/Parquet/ORC) + registry + endpoint
- Phase 45 ✅ — Sample parsers + DistributionProfiler + profile-guided Faker
- Phase 46 ✅ — Multi-file orchestrator + zip bundler + Celery + download
- Phase 47 ✅ — File output UI + generate endpoint

**v0.7 File-Based Synthetic Data Generation — shipped.**

## Tests
No new unit tests added in this plan; coverage relies on:
- Backend: existing orchestrator + bundler + writer + parser tests (44–46).
- Frontend: tsc type check covers the component surface; UI verification is
  manual (open the synthetic page, switch to File output, upload a schema in
  the existing copybook flow, then exercise the panel).

## Manual verification checklist (recommended before shipping)
- [ ] Upload a COBOL copybook via existing endpoint
- [ ] Switch to File output tab; the schema appears in the list
- [ ] Toggle on, set format = CSV, row_count = 100
- [ ] Click Generate; job_id appears
- [ ] Status transitions pending → running → completed
- [ ] Download zip succeeds; archive contains the file + manifest.json
- [ ] Same flow with format = VSAM_FIXED + EBCDIC schema produces a binary zip

---
*Phase: 47-frontend-file-output, Plan: 01 — Completed 2026-05-16*
