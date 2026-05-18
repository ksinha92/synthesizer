# Phase 61 Context — Stability + Housekeeping

> Discuss-phase output for v0.9 Integrity Gate. Auto-mode 2026-05-17. **Final phase of v0.9.**

## Vision

Fix the real SSR regression breaking `/projects`, build the Ephemeral data-copy controller (the largest open architectural decision in the milestone), and clean up the housekeeping debt — oversized files, tooling drift, version pin gaps.

## Goals

1. **F17 — `/projects` SSR `useContext` null fix.** Playwright `accessibility.spec.ts:17` catches the regression; real users hit it. Likely cause: a client-only Provider imported into a server component, or duplicate React versions. Diagnose via `npm ls react react-dom` + a clean rebuild. Fix root cause, don't suppress.

2. **F18 — Ephemeral data-copy controller (anchor work).** Today `api/v1/ephemeral.py` docstring openly admits the controller doesn't exist; rows persist forever in `pending`. **Decision locked: Docker-Compose temp containers.** Build:
   - `infrastructure/ephemeral/docker_provisioner.py` — provisions ephemeral Postgres/MySQL/MongoDB containers, applies migrations, copies (masked) data from source connection.
   - `ephemeral_tasks.py` — Celery task chain `provision → copy_data → mark_ready` with TTL-driven `expire_environment` and `revoke_environment` cleanup.
   - Lazy TTL flip removed from GET handlers (moves to background task).
   - `POST /api/v1/projects/{id}/ephemeral/{env_id}/extend` to renew TTL.
   - Connection string for the provisioned env returned in the GET response.

3. **F19 — Large-file splits.**
   - `synthetic.py` (1034 LOC) → split file-schema endpoints into `synthetic_file_schemas.py`. Routes stay at the same URLs (subrouter remount).
   - `ephemeral/page.tsx` (542 LOC) → extract `ProvisionDialog`, `RevokeDialog`, `EnvRow`, `EnvList`, `StatusPill` into `components/ephemeral/`.
   - `scheduled-jobs-panel.tsx` shim from Phase 59 → delete + remove import from `jobs/page.tsx`.

4. **F20 — Tooling pin.**
   - `backend/pyproject.toml` — pin `pytest>=8.3.0` (already pinned per Phase 57 verification), `pytest-asyncio>=0.23,<1.4` to match the available 1.3 in dev venv.
   - Resolve pnpm vs npm doc drift: project ships `package-lock.json` and `playwright.config.ts` uses `npm run dev` — align CLAUDE.md and docs to npm.

## Decisions resolved

- **Ephemeral deployment shape** → **Docker-Compose temp containers** (matches PROJECT.md "Docker Compose on VMs"). Snapshot-clone deferred to a future "Production-grade Ephemeral" milestone if Ameritas operates at a scale where temp-container spin-up becomes too slow.

## Constraints

- F18 is the largest piece — keep scope tight: provision → copy → ready. Snapshot-clone, logical-replication, and per-row sampling are explicitly v1.0 work.
- F17 must fix root cause; suppressing the test is rejected.
- F19 splits must preserve all routes/URLs (subrouter mounting).
- F20 tooling pin must not require a Docker rebuild — settings.toml changes only.
- Quality gate at v0.9 close: 154/154 backend tests was the v0.8 baseline; we're at 408+ entering Phase 61. Target ≥420 after this phase, all green except the pre-existing OIDC env failure.

## Plans

| Plan | Scope |
| --- | --- |
| **61-01** | F18 — Ephemeral data-copy controller (Docker-Compose provisioner + Celery task chain + TTL background task + extend endpoint). |
| **61-02** | F17 + F19 + F20 — SSR fix, large-file splits, tooling pin. |

---
*Created: 2026-05-17*
