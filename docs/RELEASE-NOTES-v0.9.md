# DataWrangler v0.9 — Integrity Gate

**Shipped:** 2026-05-17
**Phases:** 57–61 (5 phases, 9 plans)
**Features closed:** F1–F20 (20)
**Migrations:** 022, 024, 025, 026, 027, 028, 029 (7 new since v0.8)
**Tests:** 424 / 424 unit (+92 since v0.8 baseline), 41 / 42 integration (1 pre-existing OIDC env-fail), frontend tsc clean

## Why this milestone

The 2026-05-17 swarm evaluation (`docs/FEATURE-EVALUATION.md`) found 6 of 12 v0.8 features rated 🔴 along integration seams — features that *looked* shipped but had dead UI surfaces, empty data flows, broken async reliability, and unverifiable security claims. v0.9 closes those gaps. No new features — earn back trust before v1.0.

## What changed

### Compliance + Privacy Hub data-flow (Phase 57)
- Compliance reports now contain real PII findings, masking-rule listings, and connection inventory (handler was hard-coding empty lists).
- Compliance generation runs as a Celery task; `POST /reports` returns 202 + job_id.
- Privacy Hub `apply-all` enqueues `run_masking_task` against the default policy — bulk-apply actually masks data instead of just creating rules.
- Pre-v0.9 compliance reports flagged with `legacy=true` (migration 022).

### Dead-UI surfaces (Phase 58)
- Masking page Preview button wires `previewMasking()`.
- Subsetting `DependencyGraph` fed by `useDiscoveryStore.relationships`; edges + root highlight now render.
- Synthetic `lastConfigId` wired via store; `<QualityReport>` auto-loads after generation.
- Linked-column joint generation reachable via REST: `linked_column_ids` + `consistency_group` on `RuleCreate`/`RuleUpdate`, UI picker in the rule editor.

### Async + observability reliability (Phase 59)
- DLQ populated via Celery `task_failure` signal with **signature-aware** `job_id` resolution (signal-handler bug caught and fixed mid-phase by Codex review — `args[0]` is `policy_id`/`workflow_id`/etc. for most tasks, not `job_id`).
- All worker tasks stamp `JobModel.celery_task_id` — cancel-by-Celery-ID now works.
- `JobType` enum extended (WORKFLOW, FILE_SET, COMPLIANCE, EPHEMERAL); `_job_response` safe on unknown raw strings.
- Workflow checkpoint resume implemented (`compute_start_index` helper, 7 unit tests).
- `NODE_TIMEOUT=1800` enforced via `asyncio.wait_for`.
- Unknown workflow node types raise `ValueError` instead of silent skip.
- `quality_check` node removed from validator + dispatcher + frontend palette.
- Workflow concurrency TOCTOU fixed (`SELECT … FOR UPDATE` + migration 026 partial unique index).
- Child jobs inherit `parent_job.created_by` (no more zero-UUID).
- `WorkflowModel.schedule` column dropped (migration 025) with archive table for rollback; no production usage.
- SSE switched to Redis pub/sub with DB-poll fallback; workers publish progress events.

### Security & trust (Phase 60)
- **Webhook HMAC now verifiable.** Signs with raw secret (Fernet-encrypted at rest). 90-day deprecation window where receivers still using `secret_hash` paths see `X-Webhook-Legacy-Signing: true` header.
- `X-Webhook-Timestamp` header for replay-attack defense.
- New `webhook_deliveries` table — failed-delivery replay UI under `/admin/webhook-deliveries`.
- Celery `task_success`/`task_failure` signals fire webhooks via persistent path (no more dropped retries when per-task asyncio loop closes).
- **RBAC propagated across every feature router.** 13 routers gated via `require_project_membership(min_role)` dependency: writes need `editor`, reads need `viewer`. Migration 028 backfills existing members to `editor`; new default `viewer`.
- Dev-mode auth bypass audited — already gated on `ENVIRONMENT=='development'`. No production exposure.
- Connection preflight rate-limited (5/min per user, 429 + `Retry-After`).

### Stability + housekeeping (Phase 61)
- `/projects` SSR `useContext` null regression **fixed at the root cause**: Suspense + client providers moved into a single `Providers.tsx` client island; layout becomes a pure Server Component.
- **Ephemeral data-copy controller shipped.** Docker-Compose-spawned Postgres/MySQL/MongoDB temp containers via `DockerProvisioner` (shell-out to `docker` CLI; engine-native health checks). Celery task chain `provision → copy_data → mark_ready`. TTL background sweep extracted from GET handlers. `POST /ephemeral/{id}/extend` endpoint with 30-day cap measured from creation. Migration 029 adds controller columns.
- `synthetic.py` split (1051 → 415 LOC) — file-schema endpoints to `synthetic_file_schemas.py`, quality endpoint to `synthetic_quality.py`. All URLs preserved.
- `ephemeral/page.tsx` extracted (542 → 157 LOC) — 8 components under `frontend/src/components/ephemeral/`.
- `scheduled-jobs-panel.tsx` shim from Phase 59 deleted.
- `pytest>=8.3,<9.0` + `pytest-asyncio>=0.23,<2.0` pinned in `pyproject.toml`.
- `pnpm`/`npm` doc drift resolved — repo uses npm.

## Migration chain

```
v0.8 head: 020
v0.9 adds:
  022 legacy_compliance_reports     (Phase 57)
  024 dlq_unique_index              (Phase 59)
  025 drop_workflow_schedule        (Phase 59)
  026 workflow_unique_active_job    (Phase 59)
  027 webhook_security              (Phase 60)
  028 default_member_role_editor    (Phase 60)
  029 ephemeral_provisioning        (Phase 61)
v0.9 head: 029
```

Migration 023 number was reserved early in planning and never used; chain is intentionally non-contiguous.

## Breaking changes

- **Compliance reports generated against v0.8** contain zero PII/rule data (the bug being fixed). All such rows now carry `legacy=true`. Regenerate any required compliance artifacts post-deployment of v0.9.
- **Webhook receivers** that were validating signatures against `secret_hash` keep working for 90 days. Migrate to raw-secret HMAC during that window (recreating the webhook to get a fresh raw secret).
- **Workflows containing `quality_check` nodes** will fail validation on next execute. Edit the workflow to remove the node.
- **RBAC default for new members is `viewer`** (existing members backfilled to `editor`). Admins must promote new collaborators to editor before they can mutate project resources.
- **`WorkflowModel.schedule` field removed.** No production cron schedules were ever wired. If you had a value in the field, it's archived in `_archived_workflow_schedules` before drop.

## Deferred to v1.0

- Ephemeral masking-policy column + UI selector (`data_copy` already accepts the parameter).
- celery-beat schedule wiring for `run_ephemeral_expire_sweep_task` + `redrive_pending_webhook_deliveries`.
- Redis-backed rate-limiter for multi-worker deploys.
- Connector contract pagination (`get_sample_data` → pageable selects).
- Rule-editor `tableId` plumbing so linked-column picker is fully aware.

---

*v0.9 closed 2026-05-17 via 4-agent swarm evaluation → 5-phase milestone → ~10 parallel implementation agents across 5 work rounds. Codex stop-time review caught a real DLQ-key-conflation bug mid-phase; regression test landed alongside the fix.*
