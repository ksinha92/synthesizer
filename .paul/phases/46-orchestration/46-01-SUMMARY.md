---
phase: 46-orchestration
plan: 01
subsystem: infrastructure, messaging, api
tags: [orchestrator, multi-file, zip-bundle, celery, fk-topo-sort]
requires:
  - phase: 44-file-writers
  - phase: 45-sample-profiling
provides:
  - FileSetOrchestrator (FK topo-sort + cross-file PK propagation)
  - zip_bundler.bundle_files (manifest + per-file sha256)
  - run_file_set_generation_task Celery task
  - GET /projects/{id}/synthetic/jobs/{job_id}/file-output download endpoint
  - 6 unit tests
affects: [47-frontend]
duration: ~20min
completed: 2026-05-16
---

# Phase 46 Plan 01: Multi-File Orchestration + Zip Bundle + Celery Task + Download

**148/148 backend unit tests green (+6 from this plan).**

## Highlights
- **FileSetOrchestrator** topo-sorts schemas by cross-file FKs, raises on
  cycles, generates parent files first, then passes parent rows to
  FakerEngine so child files reference real PKs.
- **zip_bundler.bundle_files** produces an atomic-write zip with a
  `manifest.json` carrying file_set name, job + project IDs, generated_at
  timestamp, and per-file byte_count + sha256.
- **`run_file_set_generation_task`** Celery task creates a temp work dir,
  generates every file, bundles into `STORAGE_PATH/file-sets/{job_id}/{name}.zip`,
  updates JobModel with `result_summary={"bundle_path", "file_count", "file_set_name"}`.
- **Download endpoint** `GET /projects/{project_id}/synthetic/jobs/{job_id}/file-output`
  streams the zip with `media_type=application/zip` and proper filename header.
  Validates job status + bundle existence + project scoping.

## Contract for Phase 47
- Frontend kicks off generation by POSTing a FileSetDefinition; backend
  dispatches `run_file_set_generation_task.delay(...)` and returns the job_id.
- Frontend polls the job; when status="completed", calls
  `GET /jobs/{job_id}/file-output` to download.

## Edge cases handled
- FK cycle → orchestrator raises ValueError before any file is written.
- Mixed formats (CSV + Parquet in one set) → both written, both round-trip-safe.
- Zip bundle exception → write_atomic cleans up tmp file; output never visible partial.
- Job not yet completed → 409 with status. Bundle removed from disk → 410.

---
*Phase: 46-orchestration, Plan: 01 — Completed 2026-05-16*
