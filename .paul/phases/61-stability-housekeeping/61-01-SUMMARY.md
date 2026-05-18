---
phase: 61-stability-housekeeping
plans: [01, 02]
subsystem: backend, frontend, ephemeral, tooling
tags: [F17, F18, F19, F20, integrity-gate, v0.9]
features: [F17, F18, F19, F20]
requires:
  - phase: 60-security-and-trust
provides:
  - Docker-Compose ephemeral provisioner (postgres/mysql/mongo)
  - data_copy with optional masking application
  - run_ephemeral_provision_task + run_ephemeral_expire_sweep_task Celery chain
  - POST /ephemeral/{env_id}/extend (TTL capped from created_at)
  - DELETE stops container inline before flipping status
  - /projects SSR regression fixed (Providers client island)
  - synthetic.py split (1051 → 415 LOC)
  - ephemeral/page.tsx extracted (542 → 157 LOC)
  - scheduled-jobs-panel shim deleted
  - pytest + pytest-asyncio pinned
  - pnpm/npm doc drift resolved
migrations: [029_ephemeral_provisioning]
duration: ~40min (2 parallel agents)
completed: 2026-05-17
---

# Phase 61 — Stability + Housekeeping ✅ (final phase of v0.9)

## Quality gate

| Check | Result |
|---|---|
| Backend `pytest tests/unit` | **424 / 424** (+16 from 408 baseline) |
| Backend `pytest tests/integration` | 41 / 42 (OIDC env-fail unchanged) |
| Frontend `npx tsc --noEmit` | clean ✓ |
| Frontend `/projects` SSR | 200 × 8 curls, zero `useContext` errors in 319 log lines |
| Alembic head | **029** |

## What shipped (by feature)

### F17 — `/projects` SSR `useContext` null fix
**Root cause:** Next.js 14 App Router was hitting `Cannot read properties of null (reading 'useContext')` during SSR retry of the segment ErrorBoundary. Trace: `listOnTimeout → usePathname → ErrorBoundary`. Cause: `app/layout.tsx` was a Server Component that JSX-composed multiple client-side context providers (ThemeProvider wraps antd v5 ConfigProvider, plus ErrorBoundary, CommandPalette, ToastContainer) AND a `<Suspense>` boundary inline. When React's reconciler retried Suspense on a `setTimeout` cycle (antd v5 cssinjs timers), the original render dispatcher was torn down, so any hook in the segment's internal ErrorBoundary returned null.

**Fix:** centralized the whole client provider tree — including `<Suspense>` — inside a single `"use client"` `frontend/src/components/providers/Providers.tsx`. Layout becomes a pure Server Component that just mounts `<Providers>{children}</Providers>`. React owns the entire client island end-to-end.

### F18 — Ephemeral data-copy controller (anchor)
- `infrastructure/ephemeral/docker_provisioner.py` — async wrapper around `docker` CLI (run / exec health-check / stop / rm). Per-engine `_HEALTH_CHECKS` (`pg_isready`, `mysqladmin ping`, `mongosh --eval`) via `docker exec` rather than TCP probing — avoids the "TCP open but auth not loaded" false-positive on first boot.
- `infrastructure/ephemeral/data_copy.py` — connector-registry-based source→target table copy with optional masking-rule application.
- `infrastructure/messaging/ephemeral_tasks.py` — `run_ephemeral_provision_task` + `run_ephemeral_expire_sweep_task`. Updates env.status pending → provisioning → ready (or failed). publish_progress + fire_webhooks at each transition. celery_task_id stamped.
- `api/v1/ephemeral.py` refactored: POST returns 202 + job_id; GET removed write-side-effects; DELETE stops container inline before status flip; **NEW** `POST /{env_id}/extend` with TTL cap measured from `created_at` (max 30 days). Response surfaces `connection_string`, `host_port`, `container_id`.
- Migration 029 adds `container_id`, `host_port`, `connection_string`, `ready_at`, `revoked_at`, `provisioning_started_at` to `ephemeral_environments` + status/expires sweep index.
- 16 new unit tests (Docker provisioner: 7, sweep: 2, extend endpoint: 4, provision task: 3).

### F19 — Large-file splits
- `synthetic.py` 1051 → **415 LOC**. Endpoints split into `synthetic_file_schemas.py` (552 LOC — file-schema CRUD + file-set generation + file-output download) and `synthetic_quality.py` (142 LOC — `/configs/{id}/quality`). All 16 original URL paths preserved exactly via subrouter mounting.
- `ephemeral/page.tsx` 542 → **157 LOC**. Extracted: `Providers/`, `types.ts`, `utils.ts`, `StatusPill.tsx`, `EmptyState.tsx`, `EnvList.tsx`, `EnvRow.tsx`, `ProvisionDialog.tsx`, `RevokeDialog.tsx` into `components/ephemeral/`. Page now a pure refactor shell.
- `scheduled-jobs-panel.tsx` shim from Phase 59 deleted + import removed from `jobs/page.tsx`.

### F20 — Tooling pin
- `pyproject.toml` — `pytest>=8.3,<9.0`, `pytest-asyncio>=0.23,<2.0` (allows 0.23.x → 1.x; dev venv has 1.3.0, CI free to use stable 0.23).
- npm/pnpm doc drift: zero remaining `pnpm <command>` invocations in md/sh/yml/json/toml. Two historical references in `.paul/ROADMAP.md` and `docs/FEATURE-EVALUATION.md` left intact (they describe the drift being resolved, not commands).

## Inline decisions

1. **No Docker SDK dependency** — shell out via `asyncio.create_subprocess_exec` (list-form, no shell injection risk).
2. **Health checks via `docker exec`** — engine-native probes (`pg_isready`, etc.) avoid TCP-open false positives.
3. **TTL cap from `created_at`, not `now`** — prevents repeated extends from drifting the cap forward indefinitely.
4. **Container teardown before status flip on revoke** — if teardown fails, log + still flip. Orphan container > stuck row.
5. **`synthetic.py` split into 3 files** (not 2 as plan suggested) — Quality endpoint was over the 500-LOC ceiling even after file-schema extraction. Pragmatic split.
6. **F17 root cause was Suspense interaction**, not duplicate React or simple Provider import. Required moving Suspense *inside* the client boundary, not just adding `"use client"` to providers.

## Files created

| File | Purpose |
|---|---|
| `backend/app/infrastructure/ephemeral/{__init__.py, docker_provisioner.py, data_copy.py}` | F18 provisioner + copy logic |
| `backend/app/infrastructure/messaging/ephemeral_tasks.py` | F18 Celery chain |
| `backend/alembic/versions/029_ephemeral_provisioning.py` | F18 migration |
| `backend/app/api/v1/{synthetic_file_schemas.py, synthetic_quality.py}` | F19 split routers |
| `backend/tests/unit/test_docker_provisioner.py` | 7 tests |
| `backend/tests/unit/test_ephemeral_expire_sweep.py` | 2 tests |
| `backend/tests/unit/test_ephemeral_extend_endpoint.py` | 4 tests |
| `backend/tests/unit/test_ephemeral_provision_task.py` | 3 tests |
| `frontend/src/components/providers/Providers.tsx` | F17 client island |
| `frontend/src/components/ephemeral/*.tsx` (8 files) | F19 extracted components |

## Files modified

| File | Change |
|---|---|
| `backend/app/api/v1/ephemeral.py` | full refactor for F18 |
| `backend/app/infrastructure/persistence/models/ephemeral.py` | +6 controller columns |
| `backend/app/infrastructure/messaging/celery_app.py` | include `ephemeral_tasks` |
| `backend/app/api/v1/synthetic.py` | pruned to core CRUD + preview + generate + NLP |
| `backend/app/api/v1/__init__.py` | mount synthetic_file_schemas + synthetic_quality |
| `backend/pyproject.toml` | pin pytest deps |
| `frontend/src/app/layout.tsx` | slim to Server Component |
| `frontend/src/app/projects/[projectId]/ephemeral/page.tsx` | refactor shell |
| `frontend/src/app/projects/[projectId]/jobs/page.tsx` | remove shim import |

## Manual verification (live stack)

- [ ] Apply `alembic upgrade head` → reaches 029.
- [ ] POST `/api/v1/projects/<pid>/ephemeral` body `{name, ttl_hours, source_connection_id}` → 202 + job_id; poll job until `status="completed"`.
- [ ] `docker ps` shows the provisioned container.
- [ ] Connect to `host:host_port` with returned credentials — schema is present.
- [ ] POST `/ephemeral/{env_id}/extend` `{additional_hours: 24}` → expires_at extends; over-cap returns 400.
- [ ] DELETE `/ephemeral/{env_id}` → container removed from `docker ps`, row status='revoked'.
- [ ] curl `/projects` → 200, no SSR error overlay in response body.

## Carryover

- **Ephemeral masking policy column** — `data_copy` accepts `masking_policy_id` but no DB column surfaces it yet. v1.0 polish: add `masking_policy_id` to `EphemeralEnvironmentModel` + UI selector.
- **Sweep task scheduling** — `run_ephemeral_expire_sweep_task` exists but no celery-beat schedule registers it. Run manually via admin endpoint or wire when celery-beat lands (v1.0).
- **Connector contract pagination** — `get_sample_data(limit=BATCH_SIZE)` is the v0.9 contract; future pageable selects are a v1.0 connector upgrade.

---
*Phase: 61-stability-housekeeping — Completed 2026-05-17 across 2 plans. v0.9 Integrity Gate is shippable.*
