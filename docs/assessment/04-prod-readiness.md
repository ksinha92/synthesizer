# Production Readiness Assessment — DataWrangler TDM Platform

**Scope:** Ameritas internal enterprise tool, deployed on Ameritas infrastructure (not multi-tenant SaaS).
**Date:** 2026-05-17
**Method:** Read-only static review of source tree, configs, and CI workflows. App was not executed.
**Scale used:** Ready / Needs work / Missing.

---

## 1. Configuration Management — Needs work

**Evidence**

- Pydantic Settings layer is well-structured with a single source of truth and a production safety guard:
  - `backend/app/config.py:7` — `Settings(BaseSettings)` with env_file binding at `backend/app/config.py:112`.
  - `backend/app/config.py:83-110` — `enforce_production_safety()` refuses to boot when `ENVIRONMENT in {staging, production}` if `SECRET_KEY` is default, < 32 bytes, or `FERNET_KEY` is unset.
  - `backend/app/config.py:75-81` — `derive_sync_url` falls back from async URL.
- Dev/prod separation files present: `.env.example` (1-44), `.env.prod.example` (1-61), `.env` (1-30), `.env.prod` (1-18).
- `.env.prod.example` is comprehensive (`.env.prod.example:1-61`), including `FERNET_KEY` and S3 keys.

**Issues**

- MISSING — `.env.prod` (the real file, not example) is committed: `.gitignore:1-5` only ignores `.env`, not `.env.prod`. It currently holds placeholders (`CHANGE_ME_IN_PRODUCTION` at `.env.prod:3-7`) but the pattern is dangerous — anyone writing real secrets into `.env.prod` will commit them.
- Needs work — `.env.prod` is missing the `FERNET_KEY` line entirely (compare `.env.prod:1-18` vs `.env.prod.example:23`). Production boot will fail with the safety guard (good), but the live template is incomplete.
- Needs work — `CLAUDE_API_KEY` left blank in `.env.prod` (`.env.prod:14`).
- Needs work — `.env.prod` uses `datawrangler.ameritas.internal` (`.env.prod:17`) while `.env.prod.example` uses `datawrangler.ameritas.com` (`.env.prod.example:26-58`) — pick one canonical domain.

**Remediation**

- P0 — Add `.env.prod` to `.gitignore`; remove from tracking. Keep only `.env.prod.example`.
- P1 — Add `FERNET_KEY=` line to `.env.prod` template.
- P2 — Reconcile the public hostname between example and live env file.

---

## 2. Secrets Handling — Needs work

**Evidence**

- All sensitive values are typed `Settings` fields read from env (`backend/app/config.py:9-73`). No hardcoded API keys, DB passwords, or JWT secrets found in `backend/app/**/*.py`.
- Connection credentials at rest are encrypted with Fernet: `backend/app/infrastructure/security/encryption.py:15-62` (`CredentialEncryption`). Encrypted-marker scheme and key rotation API present (`encryption.py:43-57`).
- Webhook signing secrets are encrypted at rest: `encryption.py:80-101` (`encrypt_bytes` / `decrypt_bytes`).
- Constant-time API key compare: `backend/app/infrastructure/auth/jwt.py:84-87`.
- Connector error messages scrub credentials: `backend/app/infrastructure/connectors/cloud/databricks.py:24`, `redshift.py:30`, `snowflake.py:27`.

**Issues**

- Needs work — No external secrets manager integration (Vault, AWS Secrets Manager, Azure Key Vault). All secrets come from `.env`/env-vars. May be acceptable on Ameritas internal infra if the file is mounted from a vault — but should be documented.
- Needs work — JWT uses HS256 (symmetric): `backend/app/infrastructure/auth/jwt.py:14` has explicit `TODO: Use RS256/ES256 with asymmetric keys in production`. With HS256, anyone with `SECRET_KEY` can mint tokens.
- Needs work — `FERNET_KEY` rotation is single-key (`encryption.py:43-57`) — no envelope/key-versioning, so rotation requires a full re-encrypt pass with downtime risk.

**Remediation**

- P0 — Document the secrets-provisioning runbook (Vault → file vs env injection) in `docs/RUNBOOK.md`.
- P1 — Migrate JWT to RS256 (asymmetric).
- P2 — Add a key-id/version field to the Fernet ciphertext envelope so rotation can be online.

---

## 3. Error Handling & Resilience — Needs work

**Evidence**

- Global exception handlers wired in `backend/app/main.py:68-71` covering `HTTPException`, `RequestValidationError`, and generic `Exception`.
- Handlers never leak stack traces: `backend/app/middleware/error_handler.py:51-58` returns `{error: "internal_error", request_id}` while logging the full exception via structlog.
- Celery retry policies (per `DATAWRANGLER.md` spec):
  - Discovery: `max_retries=3, retry_backoff=True, retry_backoff_max=120` — `backend/app/infrastructure/messaging/discovery_tasks.py:14-19` (matches spec).
  - Masking: `max_retries=2, retry_backoff=True, acks_late=True` — `backend/app/infrastructure/messaging/masking_tasks.py:55` (matches spec).
  - Synthetic: `max_retries=2, retry_backoff=True` — `synthetic_tasks.py:14-19` (matches spec for non-LLM path).
- Dead Letter Queue: `task_failure` signal handler dead-letters once `retries >= max_retries` — `backend/app/infrastructure/messaging/celery_app.py:38-133`. Idempotent insert via `ON CONFLICT DO NOTHING` (`celery_app.py:127`). DLQ admin endpoints list/resolve/retry: `backend/app/api/v1/admin.py:210-281`.
- DLQ schema migrated: `backend/alembic/versions/024_dlq_unique_index.py`.

**Issues**

- MISSING — No LLM-specific 5x retry with jitter (`DATAWRANGLER.md` spec). The Claude provider (`backend/app/infrastructure/ai/claude_provider.py`) does not wrap calls in retry-with-jitter. Calls from `synthetic_tasks` inherit Celery's task-level retry (2x), not the spec 5x.
- MISSING — Circuit breaker declared but never used. `pybreaker>=1.2.0` is listed in `backend/pyproject.toml:19` but `grep -r "import pybreaker"` returns zero hits across `backend/app/`. External calls to OIDC IdP (`oidc.py:53-63`), Claude API, Ollama, Snowflake, and customer source DBs have no circuit breaker.
- Needs work — Celery task signature introspection in DLQ handler swallows all exceptions silently (`celery_app.py:130-133`). If DLQ DB is unhealthy, the team will never know.
- Needs work — Validation handler truncates errors aggressively: `error_handler.py:31` does `str(exc.errors()[:3])` which mixes Python repr into the JSON body.

**Remediation**

- P0 — Wrap `claude_provider.py` and `ollama_provider.py` calls with explicit retry+jitter (5x for LLM, matching spec). Consider `tenacity`.
- P0 — Add `pybreaker` around OIDC IdP, LLM providers, and per-connector external DB calls.
- P1 — Replace silent `except Exception: pass` in DLQ handler (`celery_app.py:130-133, 222-233`) with structlog warning.
- P2 — Return RFC 7807-style structured `errors` array instead of `str(exc.errors()[:3])`.

---

## 4. Logging & Observability — Needs work

**Evidence**

- `structlog` configured with JSON renderer: `backend/app/main.py:20-34`. Iso-timestamp + log level + contextvars merged in.
- Correlation IDs via `CorrelationIDMiddleware`: `backend/app/middleware/correlation.py:16-33`. Validates client-supplied UUID to prevent log injection (`correlation.py:13, 21-22`), binds into structlog context, echoes back via `X-Request-ID`.
- `/health` and `/ready` endpoints with timeouts and degraded-state semantics: `backend/app/api/v1/health.py:53-92`. DB + Redis checks (`health.py:17-50`).
- Prometheus `/metrics` endpoint: `backend/app/infrastructure/monitoring/metrics.py:33-53` — exposes `datawrangler_jobs_total{status="..."}` gauge in exposition format with JSON fallback.
- Audit-log model present: `backend/app/infrastructure/persistence/models/audit.py:13-25` with user, project, action, IP, status_code, JSONB details.

**Issues**

- MISSING — No OpenTelemetry tracing. `grep -rn "opentelemetry\|otel"` in `backend/app/` returns zero hits. Distributed tracing across FastAPI → Celery → DB is absent.
- MISSING — No `prometheus_client` library — the `/metrics` endpoint hand-rolls exposition format and exposes only 5 gauges (job counts). No request latency histogram, no Celery queue depth, no DB pool gauges.
- MISSING — Audit logging is not middleware-driven. Only ~2 endpoints actively write `AuditLog` rows: `backend/app/api/v1/admin.py:149,176,200` and one masking action (`backend/app/api/v1/masking.py`). All other mutating endpoints (project create/update/delete, connection CRUD, jobs, etc.) bypass the audit trail. This is a compliance gap.
- Needs work — No log aggregation/shipping config documented (Splunk/ELK forwarder).
- Needs work — Health check failures are logged at INFO (`health.py:28-31, 46-49`).

**Remediation**

- P0 — Add a global audit middleware (or per-router `Depends`) emitting one `AuditLogModel` row per mutating request, keyed by `request_id`. Compliance reports depend on this.
- P0 — Add `prometheus_client` and expose request latency histograms, Celery active/queued tasks, DB pool size, and DLQ depth gauges.
- P1 — Add `opentelemetry-instrumentation-fastapi` + `opentelemetry-instrumentation-celery` and ship to an OTLP collector.
- P2 — Document the Splunk/ELK log-forwarding path in `docs/DEPLOYMENT.md`.

---

## 5. Auth & Authz — Needs work

**Evidence**

- SSO via `authlib` OIDC: `backend/app/infrastructure/auth/oidc.py:21-193`. CSRF-safe state stored in Redis with 10-min TTL (`oidc.py:76-81`). `id_token` JWKS verification via `authlib.jose` (`oidc.py:152-164`). State validated atomically with `getdel` (`oidc.py:113`).
- JWT issued via `python-jose`: `backend/app/infrastructure/auth/jwt.py:17-66`. Refresh tokens have a version field for revocation (`jwt.py:31-41`).
- Rate limiting via `slowapi` on auth + assistant: `backend/app/api/v1/auth.py:60,72,153,181`, `assistant.py:52`. In-process token bucket for connection preview: `backend/app/infrastructure/auth/rate_limit.py:32-106`.
- RBAC enforcing project membership + role rank: `backend/app/infrastructure/auth/rbac.py:30-142`. Includes system-admin/owner/service-account bypass ladder (`rbac.py:75-110`).
- CORS configured explicitly (`main.py:81-89`).

**Issues**

- MISSING — slowapi uses default in-memory storage (`auth.py:30`, `assistant.py:16` — no `storage_uri` arg). `docker-compose.prod.yml:39` runs `uvicorn --workers 4`, so each worker has its own counters — effective rate limit is 4x the configured value.
- Needs work — In-process token-bucket rate limiter (`rate_limit.py:6-7` self-acknowledged): same multi-worker problem.
- Needs work — JWT HS256 (already noted in §2).
- Needs work — No CSRF protection on state-changing endpoints beyond OIDC login. JWT in `Authorization` header mitigates this for SPAs, but the cookie path is not enforced.
- Needs work — No security headers middleware (HSTS, CSP, X-Frame-Options, X-Content-Type-Options). Nginx config (`docker/nginx/nginx.conf:54-55`) only listens on port 80; no TLS, no HSTS.

**Remediation**

- P0 — Configure `slowapi.Limiter(storage_uri=settings.REDIS_URL)` so multi-worker deployments share counters.
- P0 — Move `_buckets` in `auth/rate_limit.py` to Redis (or replace with slowapi entirely once Redis-backed).
- P1 — Add a `SecurityHeadersMiddleware` setting HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy.
- P1 — Add Nginx TLS configuration with HSTS.
- P2 — Switch JWT to RS256 (see §2).

---

## 6. Database & Migrations — Ready

**Evidence**

- 29 Alembic migrations sequentially numbered: `backend/alembic/versions/001_initial_schema.py` … `029_ephemeral_provisioning.py`. Migration `023` appears skipped — verify intent.
- Connection pool configured for both async + sync engines:
  - Async: `pool_size=20, max_overflow=40, pool_timeout=30, pool_recycle=1800, pool_pre_ping=True` (`backend/app/infrastructure/persistence/database.py:21-29`).
  - Sync (Celery): `pool_size=5, max_overflow=10, pool_recycle=1800, pool_pre_ping=True` (`database.py:60-68`).
- Async session yields commit-on-exit, rollback-on-exception: `database.py:38-45`.
- Sync engine lazily initialized: `database.py:50-69`.
- Alembic uses `DATABASE_URL_SYNC` env var: `backend/alembic.ini:3`.

**Issues**

- Needs work — Migration `023` missing from linear sequence — review whether `024_dlq_unique_index.py` jump is intentional.
- Needs work — No automated migration step in `docker-compose.prod.yml` — operators must remember to run `alembic upgrade head` manually.

**Remediation**

- P1 — Add an `alembic upgrade head` init step (sidecar/init container) before backend starts in prod compose.
- P2 — Audit the missing `023` migration number.

---

## 7. Docker & Deployment — Needs work

**Evidence**

- `docker-compose.dev.yml:1-108` and `docker-compose.prod.yml:1-117` separated.
- Prod compose hides Postgres/Redis from external network (`docker-compose.prod.yml:3, 22` — no `ports:` exposed).
- Prod compose sets memory limits on each service (`docker-compose.prod.yml:18-20, 31-34, 53-56, 75-78, 87-90`).
- Prod compose adds healthchecks for Postgres and Redis (`docker-compose.prod.yml:11-15, 25-29`), with `depends_on: condition: service_healthy`.
- Frontend uses multi-stage build with Next.js standalone output and non-root `nextjs:1001` user: `frontend/Dockerfile:1-33`.

**Issues**

- MISSING — Backend Dockerfile uses `--reload` in CMD (`backend/Dockerfile:55`) — dev hot-reload flag; prod compose overrides via `command:` (`docker-compose.prod.yml:39`) but the image default is wrong.
- MISSING — Backend Dockerfile is single-stage — pulls full build toolchain (`gcc`, `g++`, `libpq-dev`, `unixodbc-dev`, `libkrb5-dev`, `msodbcsql18` …) into the runtime image (`backend/Dockerfile:13-33`).
- MISSING — Backend container runs as root — no `USER` directive in `backend/Dockerfile`. Frontend correctly drops to non-root.
- MISSING — Backend Dockerfile has no `HEALTHCHECK`.
- Needs work — Nginx is HTTP-only — `docker/nginx/nginx.conf:54-55` listens on 80, no 443, no SSL certs mounted. Prod compose exposes 443 (`docker-compose.prod.yml:96`) but nothing serves it.
- Needs work — Flower (Celery monitor) exposed unauthenticated on :5555 in prod (`docker-compose.prod.yml:106-107`) — information disclosure risk (queue state, task args).
- MISSING — No Kubernetes manifests under `/k8s`, `/helm`, `/manifests`, or `/deploy` — compose is the only deployment path. May be acceptable for Ameritas internal if compose is the target.

**Remediation**

- P0 — Convert `backend/Dockerfile` to multi-stage: `builder` stage with `gcc`/`libpq-dev`/etc, slim `runtime` with `.venv` + ODBC runtime. Drop `--reload`, add `USER appuser`, add `HEALTHCHECK CMD curl -f http://localhost:8000/health`.
- P0 — Lock Flower behind basic-auth or remove from prod compose.
- P1 — Add Nginx TLS termination block (cert paths, `ssl_protocols TLSv1.2 TLSv1.3`, HSTS header).
- P2 — Confirm with Ameritas infra team whether Kubernetes manifests are required.

---

## 8. CI/CD — Needs work

**Evidence**

- `.github/workflows/ci.yml:1-58` covers: ruff lint (`lint`), pytest with Postgres service (`backend-tests`), Next.js build (`frontend-build`).
- Pins Python 3.11 and Node 20.
- Spawns Postgres 16 service container with healthchecks for tests (`ci.yml:22-31`).

**Issues**

- MISSING — No security scanning step: no Trivy/Snyk/Grype container scan, no `pip-audit`, no `npm audit`, no Bandit/semgrep.
- MISSING — No frontend tests — only `npm run build` (`ci.yml:57`). No `npm test` / `eslint` / typecheck.
- MISSING — No image build/publish stage — CI doesn't build Docker images, so what's tested isn't what ships to prod.
- MISSING — No deploy stage — purely test-only CI. No staging deploy, no prod deploy, no rollback path defined.
- Needs work — No coverage report or threshold in pytest invocation (`ci.yml:39`).
- Needs work — `SECRET_KEY=test-secret-key` plaintext in CI env (`ci.yml:44`) — acceptable for `ENVIRONMENT=development`.

**Remediation**

- P0 — Add `trivy fs` (or `grype`) job scanning the repo + built images, gated on HIGH severity.
- P0 — Add `pip-audit` / `npm audit --omit=dev` to fail on known CVEs.
- P1 — Add a `build-images` job pushing tagged images to a private registry (e.g. Ameritas Artifactory) on tag/release.
- P1 — Add frontend `npm run lint` and `npm run typecheck`.
- P2 — Add coverage step (`pytest --cov=app --cov-fail-under=70`) and publish to PR.

---

## 9. Compliance Reporting — Ready (with audit-trail gap)

**Evidence**

- GDPR/HIPAA/CCPA reporters: `backend/app/infrastructure/compliance/gdpr_reporter.py:1-21`, `hipaa_reporter.py:1-18`, `ccpa_reporter.py:1-8`.
- PDF generation: `backend/app/infrastructure/compliance/pdf_generator.py`.
- API endpoints: `backend/app/api/v1/compliance.py:48,109,131` — generate, list, download reports.
- Migrations: `backend/alembic/versions/009_compliance_schema.py` + `022_legacy_compliance_reports.py`.
- Celery task for async generation: `backend/app/infrastructure/messaging/compliance_tasks.py`.

**Issues**

- MISSING — Audit trail completeness is the binding constraint — see §4. Reports are only as good as the `audit_logs` table they read from, and the audit table is currently only populated by a handful of admin endpoints. Reports will undercount events.

**Remediation**

- P0 — (duplicates §4) Add global audit middleware so every mutating request lands in `audit_logs`.

---

## 10. Performance & Scaling — Needs work

**Evidence**

- Chunked processing: `backend/app/infrastructure/engine/masking_engine.py:1` ("chunked processing"), `subsetting_engine.py:1` ("chunked extraction").
- CTGAN training uses configurable `batch_size`: `backend/app/infrastructure/engine/statistical_engine.py:172-181`.
- Async DB engine with pool size 20 + 40 overflow (`database.py:25-26`) supports moderate concurrency per pod.
- Prod compose runs `uvicorn --workers 4` (`docker-compose.prod.yml:39`) and `celery worker --concurrency=4` (`docker-compose.prod.yml:61`).
- Webhook re-drive task for failed deliveries: `celery_app.py:286-355`.

**Issues**

- Needs work — Horizontal scaling constrained by in-process state:
  - slowapi default storage (§5) — counters don't share across pods.
  - `rate_limit._buckets` in-process dict (`rate_limit.py:41`) — same problem.
  - OIDC state in Redis is fine (`oidc.py:81`).
- Needs work — No queue prioritization — all Celery tasks share the default queue; a slow synthetic job can starve quick discovery jobs.
- Needs work — No autoscaling hints / HPA manifests (no K8s).
- Needs work — Hardcoded memory limits in compose (`docker-compose.prod.yml:18-90`) — backend at 512m may be tight under load.

**Remediation**

- P0 — Fix shared state for rate limiting (covered in §5).
- P1 — Split Celery into named queues (`discovery`, `masking`, `synthetic`, `compliance`) with dedicated worker pools.
- P2 — Validate the 512m backend memory limit under load test before declaring prod-ready.

---

## Summary Scorecard

| # | Area | Verdict |
|---|------|---------|
| 1 | Configuration management | Needs work |
| 2 | Secrets handling | Needs work |
| 3 | Error handling & resilience | Needs work |
| 4 | Logging & observability | Needs work |
| 5 | Auth & authz | Needs work |
| 6 | Database & migrations | Ready |
| 7 | Docker & deployment | Needs work |
| 8 | CI/CD | Needs work |
| 9 | Compliance reporting | Ready (gated on §4) |
| 10 | Performance & scaling | Needs work |

**Counts:** Ready 2 · Needs work 8 · Missing 0 (per area). Within "Needs work" there are 11 P0 sub-items.

---

## Top 5 P0 Blockers

1. **`.env.prod` committed and missing `FERNET_KEY` entry** (`.gitignore:1-5`, `.env.prod:1-18`) — risk of leaking secrets if anyone updates the file with real values.
2. **Audit trail bypassed by most mutating endpoints** (only wired in `backend/app/api/v1/admin.py:149,176,200` and `masking.py`) — compliance reports will undercount; needs a global audit middleware.
3. **slowapi using in-memory storage with 4-worker uvicorn** (`backend/app/api/v1/auth.py:30`, `docker-compose.prod.yml:39`) — effective rate limits are 4× configured; must use Redis storage.
4. **Backend Dockerfile single-stage, runs as root, uses `--reload`** (`backend/Dockerfile:1, 55`) — bloated image, privilege risk, dev-default CMD.
5. **No circuit breaker for external services** (`backend/pyproject.toml:19` declares `pybreaker` but zero imports) — OIDC IdP, Claude API, Ollama, customer source DBs will cascade-fail; LLM 5x-with-jitter retry per spec also missing.
