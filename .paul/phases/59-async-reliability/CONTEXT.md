# Phase 59 Context — Async + Observability Reliability

> Discuss-phase output for v0.9 Integrity Gate. Auto-mode 2026-05-17.

## Vision

Make the job/workflow/observability plane actually do what its API surface claims. Today: DLQ table is dead (admin UI operates against an empty table), `celery_task_id` column is always NULL (cancel doesn't revoke), `JobType` enum throws on workflow jobs, workflow checkpoints are write-only (no resume), `WorkflowModel.schedule` is decorative (no celery-beat), and SSE polls the DB every 2s despite an inline comment claiming Redis pub/sub. This phase ships the reality behind those claims — or deletes the claims.

## Goals

1. **F8 — Dead-letter queue populated.** Celery `task_failure` signal handler in `celery_app.py` inserts `DeadLetterJobModel` rows when `task.request.retries >= task.max_retries`. Worker handlers write `payload` containing `connection_id` (for masking) so admin retry works.
2. **F9 — `celery_task_id` populated.** Every `_run_*_async` and Celery task body writes `task.request.id` to the JobModel before first commit. Cancel-by-Celery-ID becomes possible.
3. **F10 — `JobType` enum extended.** Add `WORKFLOW`, `FILE_SET`, `COMPLIANCE`, `EPHEMERAL`. `_job_response` tolerates unknown raw strings instead of throwing on `.value`.
4. **F11 — Workflow reliability.** Checkpoint resume reads `job.checkpoint.current_node` on retry. `NODE_TIMEOUT=1800` enforced via `asyncio.wait_for`. Unknown node types raise instead of silent-skip. `quality_check` removed from the palette (out of scope to implement now; was a no-op). TOCTOU race on concurrency check fixed with `SELECT ... FOR UPDATE` on the running-job query. Child jobs use the parent's `created_by`, not zero-UUID.
5. **F12 — Cron scheduling deleted.** Decision locked: **delete `WorkflowModel.schedule`** (no celery-beat). No production usage; field was decorative. Migration 023 drops the column. API request/response models stop accepting/returning `schedule`.
6. **F13 — SSE Redis pub/sub (publish side + opportunistic subscribe).** Workers publish progress events to Redis channel `job:{job_id}:progress` via a small helper. SSE endpoint at `events.py` tries Redis subscribe first; falls back to existing 2s DB poll if Redis unavailable. Backward compatible — no flag day.

## Decisions resolved

- **Cron scheduling** → **Delete** the `schedule` field from API + model. ROADMAP open question resolved.
- **Quality-check node** → **Remove from palette** in this phase. Not re-implementing a quality-on-workflow-completion runner yet (out of v0.9 scope).
- **DLQ payload** → standardized to `{job_type, original_args, connection_id?}` so admin retry has everything it needs.

## Constraints

- DDD: workflow validator + node-type rules stay in domain; orchestration mechanics (timeouts, signals, Redis pub/sub) stay in infrastructure.
- Idempotency: F8 must not double-insert DLQ rows on multiple failures of the same job (use `INSERT ... ON CONFLICT DO NOTHING` keyed on `original_job_id`).
- F11 checkpoint-resume must be no-op for jobs without a `checkpoint.current_node` (back-compat with existing JobModel rows).
- F13 must degrade gracefully — if Redis is down, SSE falls back to DB polling; no user-visible failure.
- F12 migration must back up `schedule` values to a JSON archive table before drop, per audit hygiene.

## Plans

| Plan | Scope |
| --- | --- |
| **59-01** | F8 + F9 + F10 — Celery signal handler, per-task celery_task_id stamping, JobType enum + `_job_response` tolerance |
| **59-02** | F11 — Workflow reliability (checkpoint resume, NODE_TIMEOUT, fail-fast, TOCTOU, created_by) |
| **59-03** | F12 + F13 — Delete schedule (migration 023) + Redis pub/sub publish + SSE subscribe with DB fallback |

---
*Created: 2026-05-17*
