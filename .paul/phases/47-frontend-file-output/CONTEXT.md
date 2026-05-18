# Phase 47 Context — Frontend File-Output Mode

> Discuss-phase output for v0.7 closure.

## Vision

Surface the v0.7 file-based generation pipeline in the UI. Users can:
1. Pick a schema source (copybook upload / Excel dictionary / from-discovery / manual).
2. Build a FileSet — one or more schemas with cross-file FKs + per-file format.
3. Launch generation; poll the job.
4. Download the resulting zip bundle when complete.

## Goals

1. New tab on the synthetic page: **"File output"**.
2. **`useFileSchemaStore`** Zustand store for the project's file schemas list.
3. **`useFileSetStore`** for the in-progress file set (schemas chosen, formats, row counts, FKs).
4. **Backend endpoint** to kick off file-set generation: `POST /projects/{id}/synthetic/file-sets/generate` returning a job_id.
5. **Schema source selector** and **file-set builder** components.
6. **Generation panel** with progress polling and zip download.

## Constraints

- Reuse existing job-polling plumbing.
- No new design system — match existing synthetic page patterns.
- Backend additions stay minimal; the heavy lift (orchestrator + writer registry + Celery + download endpoint) all landed in earlier phases.

## Plans

| Plan | Scope |
| --- | --- |
| **47-01** | Backend `POST /file-sets/generate` endpoint + frontend store + UI components + integration. Single plan since the surface is interconnected. |

---
*Created: 2026-05-16*
