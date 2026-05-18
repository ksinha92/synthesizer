---
phase: 05-discovery-pii
plan: 01
completed: 2026-03-28
duration: ~25min
---

# Phase 5 Plan 01: Schema Discovery + PII Detection Summary

**Implemented the core AI pipeline: schema discovery engine, 4-layer PII detection (regex → Presidio+spaCy → heuristics → LLM fallback), Celery async task with retry, and discovery API endpoints.**

## Objective

Automatically introspect connected databases and identify sensitive data columns with confidence scoring. This is the core value proposition — everything downstream depends on it.

## What Was Built

| File | Purpose |
|------|---------|
| `backend/app/domain/discovery/value_objects.py` | PIIType (12 types), PIIConfidence, Classification, RelationshipType enums/VOs |
| `backend/app/domain/discovery/entities.py` | DiscoveredSchema, DiscoveredTable, DiscoveredColumn (with override_by/note), DiscoveredRelationship |
| `backend/app/domain/discovery/repository.py` | DiscoveryRepository ABC: save_schema_tree, get_pii_columns, update_column_classification |
| `backend/app/domain/discovery/services.py` | SchemaDiscoveryService: connector introspection, sample masking before storage, FK extraction |
| `backend/app/domain/discovery/events.py` | DiscoveryCompleted, PIIDetected domain events |
| `backend/app/domain/shared/job.py` | Minimal Job entity (status, progress, error) for task tracking |
| `backend/app/infrastructure/ai/pii_detector.py` | PIIDetectionService: 4-layer pipeline, Presidio singleton, LLM sanitization, circuit breaker |
| `backend/app/infrastructure/persistence/models/discovery.py` | ORM models for schemas, tables, columns, relationships |
| `backend/app/infrastructure/persistence/models/job.py` | JobModel ORM |
| `backend/app/infrastructure/persistence/sqlalchemy/discovery_repo.py` | SQLAlchemy repository with entity↔model mapping, bulk save |
| `backend/app/infrastructure/messaging/discovery_tasks.py` | Celery task: 3 retries, exponential backoff (30s/60s/120s), job status tracking |
| `backend/app/application/discovery/commands.py` | RunDiscoveryCommand, OverridePIIClassificationCommand |
| `backend/app/application/discovery/queries.py` | GetDiscoveryResults, GetPIIClassifications, GetRelationships queries |
| `backend/app/application/discovery/handlers.py` | 5 handlers: RunDiscovery (concurrency limit), OverridePII, GetResults, GetPII, GetRelationships |
| `backend/app/api/v1/discovery.py` | 5 endpoints: POST /run (202), GET /results, GET /pii, PUT /columns/{id}/classification, GET /relationships |
| `backend/alembic/versions/003_discovery_schema.py` | Migration: discovered_schemas/tables/columns/relationships + jobs tables with indexes |

## Acceptance Criteria Results

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-1 | Discovery entities persist schema metadata | **PASS** | DiscoveredSchema/Table/Column entities with stats, persisted via repository, DiscoveryCompleted event emitted |
| AC-2 | 4-layer PII pipeline with weighted scores | **PASS** | Regex (0.80-0.95), Presidio (variable), Heuristics (0.60-0.80), LLM only when < 0.4. Auto-classify >= 0.65, needs-review 0.4-0.65 |
| AC-3 | Celery task with retry and progress | **PASS** | max_retries=3, retry_backoff=True (30s/60s/120s), job record created/updated, 409 on concurrent discovery |
| AC-4 | API endpoints return schema tree and PII | **PASS** | 5 endpoints with auth, schema tree (schemas→tables→columns), PII filterable by type/confidence/classification, override with audit fields |

## Key Patterns/Decisions

1. **Sample masking before storage** (audit #1) — regex-based truncate + mask (email→j***@, SSN→***-**-1234, max 50 chars, max 5 samples). Metadata store never contains raw PII.
2. **LLM prompt sanitization** (audit #2) — strip control chars, truncate (100/200 chars), XML tag separation of user data from instructions. Prevents prompt injection via malicious column names.
3. **Minimal Job entity** (audit #3) — Job + JobModel + jobs table created now instead of waiting for Phase 9. Discovery task tracks status immediately.
4. **Presidio singleton** (audit #4) — AnalyzerEngine initialized once in PIIDetectionService.__init__, reused across entire column batch. Avoids repeated 500MB spaCy model loading.
5. **Discovery concurrency limit** (audit #5) — RunDiscoveryHandler checks for active discovery per connection, returns 409 Conflict if already running.
6. **PII override audit trail** (audit #6) — override_by (UUID) and override_note fields persisted on DiscoveredColumn entity for compliance queries.
7. **Circuit breaker on LLM** — 5 failures → circuit opens, stops calling LLM for rest of batch. Graceful degradation to Layers 1-3.

## Skill Audit

/aegis:audit — not yet installed, deferred per SPECIAL-FLOWS.md.

## Next Phase

Phase 5 complete. Ready for **Phase 6: Faker Engine + LLM Provider** — Faker synthetic engine, LLM provider abstraction (Claude + Ollama), synthetic API endpoints.

---
*Completed: 2026-03-28*
