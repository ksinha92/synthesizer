# Phase 46 Context — Multi-File Generation & Orchestration

> Discuss-phase output for v0.7. Feeds `/paul:plan` for `46-01`.

## Vision

Orchestrate generation across a `FileSetDefinition`: respect cross-file FK
declarations (parent files first, child files reference the parent's primary
keys), allow each file to use a different format, bundle the resulting files
into a zip with a manifest, expose a Celery task + download endpoint.

## Goals

1. **`FileSetOrchestrator`** — topo-sort schemas by cross-file FKs, generate
   parent files first using FakerEngine, collect FK pools, pass them to
   child file generation. Mixed format per file (e.g., parent CSV, child VSAM).
2. **Zip bundler** — collect all written files + a JSON manifest into a
   single zip, named per the file set, streamable on download.
3. **Celery task** — `run_file_set_generation_task(file_set_id, project_id, job_id)`
   following the existing patterns from `synthetic_tasks.py` (status updates,
   webhook dispatch, error handling).
4. **Download endpoint** — `GET /api/v1/projects/{project_id}/synthetic/jobs/{job_id}/file-output`
   that streams the zip from storage with proper `Content-Disposition`.

## Constraints

- No new domain types — reuse `FileSchemaDefinition` / `FileSetDefinition` /
  `CrossFileFK` from Phase 43.
- Reuse `WriterRegistry.get_writer(fmt)` from Phase 44-03 for every file.
- Reuse `FakerEngine` (now profile-guided from Phase 45) for row generation.
- Reuse `write_atomic` for the zip itself.

## Plans

| Plan | Scope |
| --- | --- |
| **46-01** | FileSetOrchestrator + zip bundler + Celery task + download endpoint + tests |

---
*Created: 2026-05-16*
