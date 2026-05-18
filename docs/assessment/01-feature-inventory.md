# 01 — Feature Inventory

> Agent: `feature-scanner` (researcher)
> Method: Static analysis against `DATAWRANGLER.md` (vision) and `PLANNING.md` (sprint plan)
> Constraints: Read-only, no app execution

## Headline

**~83% of claimed features are implemented** (135 of 163 features tracked across 11 sections).

## Per-domain coverage

| Domain | Coverage |
|---|---|
| Connection | 76% |
| Discovery / PII | 71% |
| Masking | 93% |
| Synthetic | 86% |
| Subsetting | 80% |
| Workflow | 75% |
| Compliance / Audit | 83% |
| Auth / Storage / Messaging | 80% |
| Frontend / UX | 96% |
| CLI | 75% |

## Top 10 critical gaps

1. **SAML 2.0 SSO entirely absent** — only OIDC implemented.
2. **Cron-scheduled workflows** — no `schedule` column on `WorkflowModel`.
3. **Non-FK relationship inference** (naming / Jaccard / LLM) — all missing.
4. **Domain event bus** (`infrastructure/messaging/event_bus.py`) referenced but absent — events defined but never dispatched.
5. **File-format connectors** (CSV / JSON / Parquet / Avro) entirely missing.
6. **Audit middleware absent** — only explicit logging.
7. **DDD layering violations** — `domain/{masking,subsetting,compliance}/services.py` are 1-line stubs while real logic sits in `infrastructure/`.
8. **PostgreSQL BLOB storage backend** missing.
9. **Subsetting WHERE-filter** has a TODO at `subsetting_engine.py:128`, fetches in memory.
10. **TVAE / deepecho / constraint VOs** claimed but unimplemented.

## Bonus features (beyond spec)

- Ephemeral environments (Delphix-like dataPods)
- Privacy Hub
- Generator presets library
- COBOL / VSAM / EBCDIC writers
- IBM DB2 connector
- Custom sensitivity-rules engine
- Schema drift detection
- Webhook delivery queue with persistent retry

## Key evidence files

| File | What it implements |
|---|---|
| `backend/app/infrastructure/ai/pii_detector.py:1-287` | 4-layer PII detection |
| `backend/app/infrastructure/engine/masking_engine.py:1-345` | 7+ masking strategies + FPE |
| `backend/app/infrastructure/engine/statistical_engine.py:1-229` | GaussianCopula + CTGAN |
| `backend/app/infrastructure/engine/quality_evaluator.py:1-167` | KS / correlation / DCR |
| `backend/app/infrastructure/engine/subsetting_engine.py:1-196` | Subset extraction |
| `backend/app/infrastructure/engine/llm_engine.py:1-209` | LLM-based synthesis |
| `backend/app/infrastructure/connectors/{sql,nosql,cloud}/*.py` | 9 connectors |
| `frontend/src/components/workflows/workflow-canvas.tsx:1-201` | ReactFlow DAG |

**Tests on disk**: 57 backend unit tests, 15 Playwright E2E specs.

## Observations

- **Frontend is the strongest area** (96%).
- **Backend domain/infrastructure split has DDD inconsistencies** but is functionally complete.
- The codebase delivers more than the spec in some areas (ephemeral envs, Privacy Hub) while missing some core enterprise concerns (SAML, file connectors, scheduling).
