---
phase: 57-compliance-data-flow
plan: 01
subsystem: backend, compliance, privacy-hub, celery
tags: [F1, F2, F3, integrity-gate, v0.9]
features: [F1, F2, F3]
requires: []
provides:
  - GenerateReportHandler reads real PII + masking-rule + connection data
  - infrastructure/messaging/compliance_tasks.py::run_report_generation
  - POST /compliance/reports returns 202 + job_id + Location header
  - privacy_hub apply-all enqueues run_masking_task + returns job_id
  - migration 022 legacy_compliance_reports flag
duration: ~20min (2 parallel coder agents)
completed: 2026-05-17
---

# Phase 57 Plan 01 — Compliance + Privacy Hub Data-Flow ✅

## Quality gate

| Check | Result |
| --- | --- |
| Backend `pytest tests/unit` | **338 / 338 passing** (+6 from baseline 332) |
| Backend `pytest tests/integration` | 37 / 38 — pre-existing OIDC env fail unchanged |
| Compliance handler tests | 3 / 3 (new) |
| Privacy Hub apply-all tests | 3 / 3 (new) |
| Alembic head | **022** |

## What shipped

### F1 — Compliance handler reads real data
- `application/compliance/handlers.py::GenerateReportHandler.handle` now drives `ConnectionRepository`, `DiscoveryRepository`, `MaskingRepository`. Flattens to populated `pii_columns`, `masking_rules`, and `project_info.connections`.
- `infrastructure/compliance/hipaa_reporter.py` narrative refreshed — stale "Phase 18 RBAC pending" replaced with shipped-state reference to `infrastructure/auth/rbac.py` and `/admin/audit-logs`.
- GDPR + CCPA reporters reviewed — already reference shipped capabilities; no changes needed.

### F2 — Compliance generation moved to Celery
- New `infrastructure/messaging/compliance_tasks.py::run_report_generation` (max_retries=2, autoretry, acks_late). Stamps `celery_task_id` early, drives JobModel `pending → running → completed/failed`, populates `result_summary={report_id, storage_path, regulation}`, fires `job.completed`/`job.failed` webhooks. Registered in `celery_app.py::include`.
- `api/v1/compliance.py POST /reports` creates JobModel, commits, dispatches `run_report_generation.delay(...)`, returns **202 Accepted** with `Location: /api/v1/projects/<id>/jobs/<job_id>`.
- `ReportResponse` now surfaces `legacy: bool`. `AcceptedResponse(BaseModel)` added.

### F3 — Privacy Hub apply-all enqueues masking
- `api/v1/privacy_hub.py::apply_all` extended: after rule-insert + `session.flush()`, looks up first connection via `SQLAlchemyConnectionRepository.find_by_project_id(project_id, limit=1)`. If found, creates `JobModel(job_type="masking", reference_id=policy_id)`, dispatches `run_masking_task.delay(policy_id, connection_id, project_id, job_id)`, returns `job_id` on response.
- If no connection: `job_id=None`, `note="no_connection_to_mask"`. Idempotency preserved (skip-if-rule-exists path unchanged).
- `ApplyAllResponse` extended with `job_id: str | None` and `note: str | None`.

### Migration 022 — Legacy flag
- `alembic/versions/022_legacy_compliance_reports.py` adds `compliance_reports.legacy BOOLEAN NOT NULL DEFAULT false`, then `UPDATE compliance_reports SET legacy = true` so all pre-v0.9 reports are honestly flagged.
- Downgrade drops the column (additive change — fully reversible).
- `ComplianceReportModel` + `ComplianceReport` entity + `ComplianceRepository._to_entity`/`save` round-trip the flag.

## Inline decisions (vs. plan)

1. **`DiscoveredColumn.confidence_score`** doesn't exist on the entity — used `col.pii_confidence.score` instead (`domain/discovery/entities.py:51`).
2. **`MaskingRule.enabled`** doesn't exist on the entity — hard-coded `"enabled": True` in the rule payload. Reporters don't read it today; flagged for a one-line follow-up when the field lands.
3. **`ConnectionRepository.find_by_project_id`** requires `limit`/`offset` kwargs. Defaulted to `limit=100, offset=0` — adequate for typical project sizes; pagination is a future concern.
4. **GDPR + CCPA reporters** had no stale narrative strings — left unchanged per the "do not add/remove sections" constraint.
5. **`celery_task_id` is stamped** in `compliance_tasks.py` even though Phase 59 will formalize the convention. Lays groundwork.

## Files modified

| File | Change |
|---|---|
| `backend/app/application/compliance/handlers.py` | F1 — repos drive payload |
| `backend/app/infrastructure/compliance/hipaa_reporter.py` | narrative refresh |
| `backend/app/api/v1/compliance.py` | F2 — 202 + JobModel dispatch + `legacy` in response |
| `backend/app/infrastructure/messaging/celery_app.py` | include `compliance_tasks` |
| `backend/app/infrastructure/persistence/models/compliance.py` | `legacy` column |
| `backend/app/domain/compliance/entities.py` | `legacy` field |
| `backend/app/infrastructure/persistence/sqlalchemy/compliance_repo.py` | `legacy` round-trip |
| `backend/app/api/v1/privacy_hub.py` | F3 — enqueue masking + return job_id |

## Files created

| File | Purpose |
|---|---|
| `backend/app/infrastructure/messaging/compliance_tasks.py` | F2 — Celery task |
| `backend/alembic/versions/022_legacy_compliance_reports.py` | migration |
| `backend/tests/unit/test_compliance_handler.py` | F1 — 3 tests |
| `backend/tests/unit/test_privacy_hub.py` | F3 — 3 tests |

## Manual verification (runtime, against live stack)

- [ ] `curl -X POST http://localhost:8000/api/v1/projects/<pid>/compliance/reports -d '{"regulation":"hipaa"}'` returns **202** with `{job_id, status:"pending"}` and `Location` header. Apply migration 022 first via `alembic upgrade head`.
- [ ] After job completes (poll `/api/v1/projects/<pid>/jobs/<job_id>`), download the PDF — should contain non-zero `pii_columns` and `masking_rules` against a project with real discovery data.
- [ ] `GET /api/v1/projects/<pid>/compliance/reports` surfaces `legacy: true` for pre-v0.9 rows.
- [ ] `curl -X POST http://localhost:8000/api/v1/projects/<pid>/privacy-hub/apply-all -d '{"pii_types":["email"]}'` returns `job_id`. Job log shows `run_masking_task` ran.

## Carryover to next phases

- **`celery_task_id` populated** in compliance task lays Phase 59 F9 groundwork — masking/discovery/synthetic/subsetting/workflow tasks still need the same treatment.
- **`JobType.COMPLIANCE`** value used as raw string `"compliance"` — Phase 59 F10 will extend the enum to include it.

---
*Phase: 57-compliance-data-flow, Plan: 01 — Completed 2026-05-17*
