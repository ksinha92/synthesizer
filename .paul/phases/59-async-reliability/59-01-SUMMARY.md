---
phase: 59-async-reliability
plans: [01, 02, 03]
subsystem: backend, celery, sse, redis, workflow, jobs
tags: [F8, F9, F10, F11, F12, F13, integrity-gate, v0.9]
features: [F8, F9, F10, F11, F12, F13]
requires:
  - phase: 58-dead-ui-surfaces
provides:
  - Celery task_failure signal inserts DLQ rows on retry exhaustion (signature-aware job_id lookup)
  - All worker tasks stamp JobModel.celery_task_id
  - JobType enum WORKFLOW/FILE_SET/COMPLIANCE/EPHEMERAL + safe _job_response
  - Workflow checkpoint resume (compute_start_index helper)
  - NODE_TIMEOUT=1800 enforced via asyncio.wait_for
  - Unknown workflow node types fail fast (ValueError)
  - quality_check node removed from validator + palette + dispatch
  - Workflow concurrency TOCTOU fixed (with_for_update + partial unique index)
  - Child jobs inherit parent created_by
  - WorkflowModel.schedule column dropped (migration 025)
  - Redis pub/sub publish from all workers + SSE Redis-first subscribe with DB-poll fallback
  - get_sync_session helper for Celery signal handlers
migrations: [024_dlq_unique_index, 025_drop_workflow_schedule, 026_workflow_unique_active_job]
duration: ~50min (3 plans, 4 sequential agents — Round 1 parallel, Round 1.5 fix, Round 2 sequential)
completed: 2026-05-17
---

# Phase 59 — Async + Observability Reliability ✅

## Quality gate

| Check | Result |
|---|---|
| Backend `pytest tests/unit` | **383 / 383** (+43 from 340 baseline — +20 from Round 2 alone) |
| Backend `pytest tests/integration` | 39 / 40 (OIDC env-fail unchanged) |
| Frontend `npx tsc --noEmit` | clean ✓ |
| Alembic head | **026** |

## What shipped (by feature)

### F8 — DLQ task_failure signal
- `celery_app.py::_handle_task_failure_to_dlq` gates on `retries >= max_retries`, **inspects `inspect.signature(sender.run)` to find the `job_id` parameter position** (Codex caught a v0.8-style bug here — `args[0]` is `policy_id`/`workflow_id`/`config_id` for most tasks, NOT `job_id`).
- Insert via `INSERT ... ON CONFLICT(original_job_id) DO NOTHING` (migration 024 partial unique index).
- Exception swallowed — DLQ failure must never crash a worker.
- 7 unit tests including **2 regression tests** verifying masking (args[3]) and workflow (args[2]) signatures pick the correct slot.

### F9 — `celery_task_id` stamping
- All 6 worker tasks (`discovery`, `masking`, `synthetic` x 2, `subsetting`, `workflow`) stamp `JobModel.celery_task_id = self.request.id` on entry.
- Compliance task already had this from Phase 57.
- `_celery_task_id_stamped` test verifies first-time stamp + no-overwrite on retry.

### F10 — JobType enum extension
- `domain/shared/job.py::JobType` now has all 8 values.
- `api/v1/jobs.py::_safe_job_type` helper falls back to `"unknown"` on AttributeError/ValueError. Used by both `_job_response` and `_job_detail_response`.

### F11 — Workflow reliability
- `compute_start_index(checkpoint) -> int` pure helper (7 unit tests for resume math).
- `asyncio.wait_for(_execute_node, timeout=NODE_TIMEOUT)` enforced.
- Unknown node types raise `ValueError`.
- `quality_check` removed from `workflow_tasks.py`, `domain/workflow/services.py::VALID_NODE_TYPES`, `EDGE_RULES`, `NODE_TYPE_ALIASES`, and frontend `node-palette.tsx`/`node-types.tsx`/`workflow-canvas.tsx`/`node-config-panel.tsx`.
- TOCTOU race fixed: `.with_for_update()` on running-job SELECT in `ExecuteWorkflowHandler`, plus migration 026 partial unique index on `jobs(reference_id) WHERE status IN ('pending','running') AND job_type='workflow'`.
- Child jobs inherit `parent_job.created_by` (no more zero-UUID).

### F12 — `WorkflowModel.schedule` deleted
- Migration 025: archives non-null schedules to `_archived_workflow_schedules` then drops column. Downgrade restores from archive.
- Removed from domain entity, ORM model, repo, command, handler, API schemas, frontend types, cron-editor UI, `scheduled-jobs-panel.tsx` shimmed to no-op (back-compat for `jobs/page.tsx` import).

### F13 — SSE Redis pub/sub
- New `infrastructure/messaging/progress_pubsub.py` with `publish_progress()` (sync; swallows errors), `subscribe_progress()` (async generator), `channel_for()`.
- All 7 worker tasks call `publish_progress` at every status/progress commit boundary (including failure path).
- `api/v1/events.py::_progress_stream` tries Redis first with 30s heartbeat; falls back to existing DB poll on any exception. Backward-compatible.

## Inline decisions (vs. plan)

1. **DLQ signal handler used `args[0]`** initially — Codex stop-time review caught the bug. Fixed mid-phase: now uses `inspect.signature(sender.run)` to find `job_id` parameter slot. Two regression tests landed alongside.
2. **TOCTOU index column**: plan said `workflow_id`; actual schema uses generic `JobModel.reference_id` keyed by `job_type='workflow'`. Migration 026 uses partial index on `(reference_id) WHERE ... AND job_type='workflow'`.
3. **`quality_check` removal cascades**: `EDGE_RULES` removal makes `masking` terminal (it previously only flowed into `quality_check`). Frontend default DAG retuned from `discovery → masking → quality_check` to `discovery → subsetting → masking` so the default linear DAG still validates.
4. **`get_sync_session` helper** didn't exist; added lazy psycopg2 engine in `infrastructure/persistence/database.py`. Celery signal handlers aren't on the asyncio loop, so they need sync.
5. **`compute_start_index` extracted** as a pure helper for cheap unit testing rather than mocking the whole `_run_async` body.

## Files modified

29 backend files, 5 frontend files. See plan files 59-01, 59-02, 59-03 for the full breakdown. Highlights:
- `backend/app/infrastructure/messaging/{celery_app,discovery_tasks,masking_tasks,synthetic_tasks,subsetting_tasks,workflow_tasks,compliance_tasks,progress_pubsub}.py`
- `backend/app/domain/{shared/job,workflow/services,workflow/entities}.py`
- `backend/app/application/workflow/{commands,handlers}.py`
- `backend/app/api/v1/{jobs,events,workflows}.py`
- `backend/app/infrastructure/persistence/{database,models/workflow,sqlalchemy/workflow_repo}.py`
- `backend/alembic/versions/{024,025,026}_*.py`
- `frontend/src/components/workflows/{node-palette,node-types,workflow-canvas,workflow-editor,node-config-panel}.tsx`
- `frontend/src/components/jobs/scheduled-jobs-panel.tsx` (shim)
- `frontend/src/stores/workflow-store.ts`
- `frontend/src/app/projects/[projectId]/workflows/[workflowId]/page.tsx`

## Test results

- 20 new tests this phase (43 cumulative for v0.9 so far).
- Test files added: `test_dlq_signal.py`, `test_job_type_enum.py`, `test_progress_pubsub.py`, `test_workflow_no_schedule.py`, `test_events_sse_fallback.py`, `test_workflow_checkpoint_resume.py`, `test_workflow_node_timeout.py`, `test_workflow_unknown_node_fails_fast.py`, `test_quality_check_removed.py`, `test_celery_task_id_stamped.py`.

## Carryover

- **Existing workflows containing a `quality_check` node** will fail validation on next execute. Flag in release notes; users must remove the node manually.
- **`scheduled-jobs-panel.tsx`** is a no-op shim. Follow-up: remove the import from `jobs/page.tsx` and delete the file.
- **Migration 023** number was never used (sequence is now 022 → 024 → 025 → 026). Acceptable — alembic doesn't require contiguous integers.

---
*Phase: 59-async-reliability — Completed 2026-05-17 across 3 plans*
