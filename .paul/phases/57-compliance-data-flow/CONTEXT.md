# Phase 57 Context — Compliance + Privacy Hub Data-Flow

> Discuss-phase output for v0.9 Integrity Gate. Auto-mode recommendations selected 2026-05-17.

## Vision

Fix the three "looks done, isn't" data-flow gaps in the v0.8 release surface. Today every HIPAA/GDPR/CCPA PDF ships with zero findings, the Privacy Hub `apply-all` button creates rules without ever masking data, and compliance generation blocks the request thread. After Phase 57: reports contain real PII + rule data, generation runs async with progress, and Privacy Hub bulk-apply actually masks.

## Goals

1. **Wire compliance reports to real data.** `application/compliance/handlers.py::GenerateReportHandler.handle` reads from `DiscoveryRepository` and `MaskingRepository` instead of passing hard-coded empty lists at lines 41-43. Reporter classes (`hipaa_reporter.py`, `gdpr_reporter.py`, `ccpa_reporter.py`) get populated `pii_columns`, `masking_rules`, and `project_info.connections`. Stale "Phase 18 RBAC pending" narrative (`hipaa_reporter.py:33`) refreshed to reflect shipped RBAC.

2. **Move compliance generation off the request thread.** New `infrastructure/messaging/compliance_tasks.py::run_report_generation` Celery task. `api/v1/compliance.py` returns `202 Accepted` + `job_id` + `Location` header. Existing GET endpoints (download, list) unchanged. Progress surfaces through the standard JobModel + SSE plane.

3. **Privacy Hub `apply-all` actually masks data.** `api/v1/privacy_hub.py:262-320` enqueues `run_masking_task` for the default policy after rule creation. Response shape adds `job_id` so the UI can poll for completion. Existing idempotency (skip-if-rule-exists) preserved.

## Decisions resolved in this discuss

- **Compliance back-fill policy** → **Label archived reports "pre-v0.9 placeholder"**, do not regenerate. Audit-honest; preserves history. Migration adds a `legacy: bool` column on `ComplianceReportModel` flipped to `True` for all pre-v0.9 rows.

## Constraints

- DDD: handler stays a domain orchestrator. Repo access is via the existing `DiscoveryRepository` + `MaskingRepository` interfaces; no new infrastructure abstractions.
- All three reporters (HIPAA, GDPR, CCPA) get the fix in one change — equal-priority constraint from PROJECT.md.
- Compliance Celery task uses the same `JobModel` plane every other long-running task uses (no parallel state machines).
- Privacy Hub `apply-all` job uses `JobType.MASKING` (or `JobType.WORKFLOW` if a future enum extension lands in Phase 59); existing masking task's idempotency contract is sufficient.
- No new migrations for F1/F2/F3 themselves; one small migration `022_legacy_compliance_reports.py` for the back-fill flag.
- Legal/compliance team must re-review report content after F1 lands.

## Plans

| Plan | Scope |
| --- | --- |
| **57-01** | F1 + F2: wire repos into compliance handler, refresh reporter narratives, ship `compliance_tasks.py` Celery task, update `api/v1/compliance.py` to return 202 + job_id, migration 022 for `legacy` flag. Plus F3: `privacy_hub.py:apply-all` enqueues `run_masking_task` and returns `job_id`. Unit + integration tests covering all three. |

---
*Created: 2026-05-17*
