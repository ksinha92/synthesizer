---
phase: 60-security-and-trust
plans: [01, 02]
subsystem: backend, security, webhooks, auth, rbac, rate-limit
tags: [F14, F15, F16, integrity-gate, v0.9]
features: [F14, F15, F16]
requires:
  - phase: 59-async-reliability
provides:
  - Webhook HMAC signs with raw secret (Fernet-encrypted at rest)
  - X-Webhook-Timestamp + 5-min skew window
  - X-Webhook-Legacy-Signing header during 90-day deprecation
  - webhook_deliveries table for failed-delivery replay
  - GET /admin/webhook-deliveries + POST /admin/webhook-deliveries/{id}/retry
  - Celery task_success/task_failure signals fire job.completed/job.failed webhooks
  - redrive_pending_webhook_deliveries() helper for periodic redrive
  - require_project_membership(role) dependency
  - 13 feature routers gated (writes=editor, reads=viewer)
  - Connection preflight rate-limit (5/min, 429 with Retry-After)
  - Existing project_members.role NULL/empty → editor; new default viewer
  - dev-bypass already gated on ENVIRONMENT=='development' (audited)
migrations: [027_webhook_security, 028_default_member_role_editor]
duration: ~25min (2 parallel agents)
completed: 2026-05-17
---

# Phase 60 — Security & Trust ✅

## Quality gate

| Check | Result |
|---|---|
| Backend `pytest tests/unit` | **408 / 408** (+25 from 383 baseline) |
| Backend `pytest tests/integration` | 41 / 42 (OIDC env-fail unchanged) |
| Frontend `npx tsc --noEmit` | clean ✓ |
| Alembic head | **028** |

## What shipped (by feature)

### F14 — Webhook HMAC fix + deliveries audit
- `dispatcher.py::_sign` signs HMAC with **raw secret** (Fernet-decrypted from `secret_encrypted`). Receivers can verify using the raw secret returned at creation.
- Signing string: `f"{ts}.{body}"`. Timestamp emitted as `X-Webhook-Timestamp` header.
- **90-day deprecation window**: webhooks with only `secret_hash` (no `secret_encrypted`) and `legacy_signing=True` continue to sign with `secret_hash` AND emit `X-Webhook-Legacy-Signing: true` header — receivers see the deprecation explicitly. New webhooks created post-v0.9 set `legacy_signing=False` and use raw-secret path exclusively.
- **`encrypt_bytes` / `decrypt_bytes`** helpers added to `infrastructure/security/encryption.py` — webhook secrets need raw-byte round-trip (connections use JSON-dict). Both share `FERNET_KEY`.
- New `webhook_deliveries` table tracks every dispatch (pending → sent | failed). `admin_router` exposes list + manual retry.
- `task_success`/`task_failure` Celery signals fire `job.completed`/`job.failed` webhooks via persistent path; failure path gated on retry exhaustion (mirrors DLQ).
- `redrive_pending_webhook_deliveries(limit=100)` async helper for periodic redrive (no beat-schedule wiring yet — out of scope).
- Drive-by: structlog reserved-kwarg fix (`event=` → `event_type=`) in `fire_webhooks` — latent TypeError uncovered now that the path runs in tests.

### F15 — RBAC propagation
- `infrastructure/auth/rbac.py::require_project_membership(min_role)` dependency. Access ladder: system admin → service-account → project owner → `project_members.role >= min_role`. 403 with `{error, project_id}` otherwise.
- **13 feature routers gated**: connections (11 endpoints), discovery (5), masking (8), synthetic (14), subsetting (5), workflows (5), jobs (4), compliance (3), ephemeral (3), privacy_hub (2), database_view (3), plus generator_presets (5) and sensitivity_rules (5) on tenant-wide `require_editor`/`require_viewer` because those routes aren't project-scoped.
- `projects.py` left alone (already uses `_get_owned_project`).
- Migration 028 backfills `project_members.role` NULL/empty → `editor`; new column default `viewer`. Admins promote.
- Dev-bypass already gated on `settings.ENVIRONMENT == "development"` — audited, no change required.

### F16 — Connection preflight rate-limit
- New `infrastructure/auth/rate_limit.py` — in-process token bucket, keyed `{user_id}:{request.url.path}`. 5/min default. 429 with `Retry-After` header when empty.
- Applied to `connections.py::preflight` endpoint.
- Exposes `_buckets` + `_reset_buckets()` for hermetic tests.

## Inline decisions (vs. plan)

1. **Plan referenced `members` table; actual is `project_members`** (migration 010). Dependency uses `ProjectMemberModel` directly with lazy imports.
2. **`generator_presets` + `sensitivity_rules` aren't project-scoped** — used tenant-wide `require_editor`/`require_viewer` instead of `require_project_membership`. Intent preserved.
3. **Migration ordering**: F15 agent shipped 028 first (member-role default) before F14 shipped 027 (webhook security). Chain healed: 026 → 027 → 028.
4. **`encrypt_bytes` helper added** rather than reusing `CredentialEncryption.encrypt` (which JSON-serializes a dict). Webhook secrets are opaque bytes.
5. **`redrive_pending_webhook_deliveries`** exposed as async function, not a Celery beat task — no beat infrastructure exists today. Available via admin manual-retry endpoint.

## Files modified

| File | Change |
|---|---|
| `backend/app/infrastructure/persistence/models/webhook.py` | +secret_encrypted, +legacy_signing |
| `backend/app/infrastructure/webhooks/dispatcher.py` | raw-secret HMAC + timestamp + persistence |
| `backend/app/infrastructure/security/encryption.py` | +encrypt_bytes/decrypt_bytes |
| `backend/app/infrastructure/messaging/celery_app.py` | signal handlers fire webhooks via persistent path |
| `backend/app/api/v1/webhooks.py` | encrypt-on-create + admin endpoints |
| `backend/app/api/v1/__init__.py` | mount admin_router |
| `backend/app/infrastructure/auth/rbac.py` | +require_project_membership |
| `backend/app/api/v1/*.py` (13 routers) | dependency injection |
| `backend/alembic/env.py` | register new models |

## Files created

| File | Purpose |
|---|---|
| `backend/app/infrastructure/persistence/models/webhook_delivery.py` | WebhookDeliveryModel |
| `backend/app/infrastructure/auth/rate_limit.py` | token-bucket limiter |
| `backend/alembic/versions/027_webhook_security.py` | F14 migration |
| `backend/alembic/versions/028_default_member_role_editor.py` | F15 migration |
| `backend/tests/unit/test_webhook_hmac_raw_secret.py` | F14 tests |
| `backend/tests/unit/test_webhook_legacy_signing_deprecation.py` | F14 deprecation tests |
| `backend/tests/unit/test_webhook_delivery_persistence.py` | F14 persistence tests |
| `backend/tests/unit/test_webhook_timestamp_window.py` | F14 timestamp tests |
| `backend/tests/unit/test_rbac_dependency.py` | F15 RBAC tests (9 cases) |
| `backend/tests/unit/test_rate_limit_token_bucket.py` | F16 limiter tests (5 cases) |
| `backend/tests/integration/test_dev_bypass_gated.py` | dev-bypass audit |

## Carryover

- **Webhook beat schedule** for `redrive_pending_webhook_deliveries` — leave for v1.0 if needed. The admin retry endpoint works manually.
- **Generator presets + sensitivity rules** could be made project-scoped in v1.0 if we want per-project libraries. Currently tenant-wide.
- **Rate limiter is in-process** — multi-worker deploys need Redis-backed limiter in v1.0.

---
*Phase: 60-security-and-trust — Completed 2026-05-17 across 2 plans*
