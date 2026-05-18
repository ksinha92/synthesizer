# DataWrangler — Production-Grade Assessment Summary

> Synthesized from 4 read-only agent reports run 2026-05-17.
> Source reports: `01-feature-inventory.md`, `02-test-results.md`, `03-code-gaps.md`, `04-prod-readiness.md`

## Bottom line

DataWrangler is **functionally further along than its file structure suggests** — ~83% of claimed features have real implementations, all 9 connectors and both LLM providers ship working code, and the frontend is 96% complete. **However, there are 3 silent-failure bugs that would ship broken features, a committed `.env.prod` (secrets-leak vector), and a JWT signing scheme that's not enterprise-grade.** Production deployment is **NOT ready** until P0 items are cleared.

## Scoreboard

| Dimension | Score |
|---|---|
| Feature implementation (vs spec) | 83% |
| Frontend completeness | 96% |
| Backend bounded-context completeness | 88% avg (range: synthetic 100% → subsetting 63%) |
| Tests passing (Playwright chromium real) | 134/141 (95%) |
| Tests blocked by environment | Firefox 148, Jest n/a, pytest 64 files |
| Production readiness areas Ready / Needs work / Missing | 2 / 8 / 0 |

---

## P0 — Must fix before any deploy (security + silent failures)

| # | Issue | Evidence | Effort |
|---|---|---|---|
| P0-1 | **`.env.prod` is committed to git** and missing `FERNET_KEY` — secrets-leak vector | `.gitignore:1-5` only ignores `.env` (not `.env.prod`) | 15 min: gitignore + rotate any leaked keys + add `FERNET_KEY` |
| P0-2 | **JWT signs with HS256 + shared secret** — not enterprise-grade | `infrastructure/auth/jwt.py:14` | 1d: switch to RS256 + key rotation |
| P0-3 | **Masking preview runs against empty dataset `[]`** — silent feature failure shipping bad UX | `application/masking/handlers.py:82` | 2h |
| P0-4 | **Subsetting validates WHERE filter then discards it**, pulls all rows in-memory — silent feature failure + perf bomb | `infrastructure/engine/subsetting_engine.py:126-128` | 4h |
| P0-5 | **Audit trail is not middleware-driven** — only 4 explicit call sites write `AuditLog`, so GDPR/HIPAA/CCPA reports undercount | `admin.py:149,176,200`, `masking.py:*` | 1d: FastAPI middleware that auto-logs on each authed request |
| P0-6 | **slowapi rate-limit uses in-memory storage** under uvicorn `--workers 4` — effective limit is 4× the configured value | `auth.py:30`, `docker-compose.prod.yml:39` | 2h: swap to Redis-backed limiter |
| P0-7 | **Backend Dockerfile runs as root** + CMD ends with `--reload` — dev mode in prod | `backend/Dockerfile:1,55` | 2h: multi-stage, non-root user, gunicorn or uvicorn-prod CMD |
| P0-8 | **`pybreaker` declared but never imported** anywhere — no circuit breakers; LLM 5x-retry-w/-jitter from spec missing | grep `pybreaker` returns 0 hits in `backend/app/` | 1d |
| P0-9 | **`discovery_repo.delete()` is `pass`** with a misleading "cascade handled" comment, but no FK actually cascades | discovery repo file | 1h |

**Estimated P0 effort: ~5–6 dev-days.**

---

## P1 — Required for "production-grade" claim

### Security / Auth
- **SAML 2.0 SSO entirely missing** — only OIDC implemented (`feature-scanner` finding). Enterprise-internal Ameritas deployment likely requires SAML.
- JWT key rotation + token revocation list.

### Resilience / Observability
- Wire Celery retry policies to spec: discovery 3x (30s/60s/120s), masking 2x, LLM 5x w/ jitter.
- Dead-letter queue verification + alerting.
- Health/readiness endpoints (`prod-validator` flagged as Needs work).
- Request correlation IDs propagating into Celery tasks.

### Tests — unblock the 64 backend test files
1. Install `pytest` into `backend/.venv` (dev extras not installed).
2. Install Playwright Firefox binary: `cd frontend && npx playwright install firefox` (clears 148 false failures).
3. Install `ts-node` in `frontend/node_modules` so `jest.config.ts` can load.
4. Add actual frontend Jest unit tests — currently **zero** exist; all frontend tests are e2e.

### 7 real chromium Playwright failures (product bugs)
- Project Detail Page workspace tablist not rendering (3 tests)
- AI Assistant Sidebar `text=Synthia` selector ambiguity (3 tests)
- Workflows node-type dropdown shows 4 options instead of 5 (1 test)

### Compliance
- Compliance reports gated on audit gap (P0-5). Cannot trust output until that's fixed.

---

## P2 — Feature gaps to plan into next sprints

From `01-feature-inventory.md` top gaps:

1. **Cron-scheduled workflows** — `WorkflowModel.schedule` column missing
2. **Non-FK relationship inference** (naming similarity / Jaccard / LLM) — all missing
3. **Domain event bus** (`infrastructure/messaging/event_bus.py`) — referenced but absent; events defined but never dispatched
4. **File-format connectors** (CSV / JSON / Parquet / Avro) — entirely missing
5. **PostgreSQL BLOB storage backend** — missing
6. **TVAE / deepecho / constraint VOs** — claimed but unimplemented
7. **Schema drift module** (`domain/connection/schema_drift.py`) — built but never wired; `block_on_schema_change` toggle is dead code

### DDD cleanup
- `domain/{masking,subsetting,compliance}/services.py` are 1-line stubs while real logic sits in `infrastructure/` — violates the DDD contract in `CLAUDE.md` ("domain layer has zero framework dependencies").
- Bounded-context weakest links: `workflow` (75%), `compliance` (63%), `subsetting` (63%) — all skip domain repository ABCs and value-objects modules.

---

## What's working well (don't break it)

- **Frontend (96%)** — Next.js 14 + Ant Design + ReactFlow workspace canvas is solid; 134/141 Playwright tests pass
- **Synthetic engines (100% bounded-context complete)** — Faker / Statistical (GaussianCopula + CTGAN) / LLM all real implementations
- **Masking engine** — 7+ strategies + Format-Preserving Encryption (FPE) at `masking_engine.py:1-345`
- **PII detection** — 4-layer Presidio + custom rules at `pii_detector.py:1-287`
- **Quality evaluator** — KS test, correlation matrices, DCR at `quality_evaluator.py:1-167`
- **29 sequential Alembic migrations** — DB & migrations is one of only 2 areas marked Ready
- **Bonus features beyond spec**: Ephemeral environments (Delphix-like dataPods), Privacy Hub, generator presets, COBOL/VSAM/EBCDIC writers, IBM DB2 connector, custom sensitivity rules, schema-drift detection (just unwired), webhook delivery queue

---

## Recommended next 2-week sprint

**Week 1 — P0 sweep (parallelizable):**
- Day 1: P0-1 (gitignore + rotate), P0-3 (masking preview), P0-4 (subsetting WHERE), P0-9 (delete cascade)
- Day 2-3: P0-5 (audit middleware), P0-6 (Redis rate limiter), P0-7 (Dockerfile prod-hardening)
- Day 4-5: P0-2 (JWT RS256), P0-8 (pybreaker + Celery retry policies)

**Week 2 — Test infra + 7 real bugs:**
- Day 1: Install Playwright Firefox, install pytest, install ts-node → get a green baseline
- Day 2-3: Fix 7 chromium Playwright failures (real product bugs)
- Day 4-5: SAML SSO scaffolding (P1 critical for Ameritas)

After this, the platform can credibly be called production-ready for an Ameritas-internal deployment.
