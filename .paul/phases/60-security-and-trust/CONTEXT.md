# Phase 60 Context — Security & Trust

> Discuss-phase output for v0.9 Integrity Gate. Auto-mode 2026-05-17.

## Vision

Make the security surfaces match the documentation. Today webhook HMAC signatures can't be verified by receivers (key is `secret_hash`, receivers only have raw secret), RBAC is only enforced on admin + webhooks endpoints (every other feature is identity-only), and connection preflight has no rate limit (SSRF risk from authenticated users).

## Goals

1. **F14 — Webhook HMAC verifiable + delivery audit.**
   - Sign HMAC with **raw secret** (encrypted at rest via Fernet, decrypted at dispatch). Receivers using the secret they were shown at creation time can now verify.
   - Add `X-Webhook-Timestamp` header + verify timestamp window server-side (5 min skew tolerance).
   - New `webhook_deliveries` table for failed-delivery replay (status, attempts, last_error, next_retry_at).
   - Dispatch moves to Celery signal handlers so retry tail isn't dropped when the per-task event loop closes.
   - **Migration 027** + **deprecation window**: both `secret_hash`-based AND raw-secret-based signatures accepted server-side for 90 days. Existing webhooks ship a `legacy_signing: bool` flag.

2. **F15 — RBAC propagation.**
   - Extend `require_role(editor|viewer|admin)` from `admin.py` + `webhooks.py` to every feature router (Connections, Discovery, Masking, Synthetic, Subsetting, Workflows, Jobs, Compliance, Ephemeral, Privacy Hub, Database View, Generator Presets, Sensitivity Rules).
   - Standardize project-ownership check via shared `require_project_membership(role)` dependency.
   - **Default for existing users:** `editor` — preserves current behavior. New users default `viewer`; promoted by admin.
   - Audit and **close the dev-bypass**: `GET /api/v1/projects` returns 200 without auth in dev — confirm this is `ENV=development` only and not deployed.

3. **F16 — Connection preflight rate-limit.**
   - `POST /api/v1/projects/{id}/connections/preflight` adds per-user rate limit (5 req/min) via in-memory token bucket on the dependency layer. Avoids SSRF/internal port-scan abuse.
   - No new dependency — implement with `time.monotonic()` and a small dict; document the in-process limitation (multi-worker scenarios need Redis-backed limiter later).

## Decisions resolved

- **RBAC default for existing users** → **`editor`**. Migration 028 writes the role for every existing `members` row.
- **Webhook secret migration** → **90-day deprecation window**. Both signature paths accepted; receivers see a deprecation header `X-Webhook-Legacy-Signing: true` so they can rotate proactively.
- **Rate-limit storage** → **in-process** for v0.9. Redis-backed limiter for v1.0 if we add a second app worker.

## Constraints

- DDD: signature logic lives in `infrastructure/webhooks/`. RBAC logic stays in `infrastructure/auth/`. Routers consume dependencies, no inline policy.
- All migrations additive and reversible.
- No breaking changes to existing webhook receivers — deprecation window protects them.
- Rate limiter must degrade gracefully under load (no exceptions on bucket misses).
- Project-ownership checks must work across all auth modes (SSO + JWT + dev bypass).

## Plans

| Plan | Scope |
| --- | --- |
| **60-01** | F14 — Webhook security: raw-secret HMAC + deliveries table + timestamp header + 90-day deprecation + signal-handler dispatch (migration 027). |
| **60-02** | F15 + F16 — RBAC propagation across all feature routers + project-ownership consistency + connection preflight rate-limit + RBAC default editor migration (028). |

---
*Created: 2026-05-17*
