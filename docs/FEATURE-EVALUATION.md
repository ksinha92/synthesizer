# DataWrangler Feature Evaluation — 2026-05-17

Swarm-based evaluation of 12 features across backend, frontend, workflow integration, tests, and live-stack runtime probes. **Report only — no code fixes.**

**Method**: 4 specialized agents (backend, frontend, workflow, tests) audited the live `main` branch against the running stack (backend `:8000`, frontend `:3000`). Findings below are cited file:line from agent outputs.

Legend: 🟢 functional · 🟡 partial / known gaps · 🔴 broken or missing · ⚪ n/a or no data

## Summary

| Feature | Backend | Frontend | Workflow | Tests | Runtime | Overall |
|---|---|---|---|---|---|---|
| Privacy Hub | 🟡 | 🟢 | 🔴 | 🟢 | 🟢 | 🔴 |
| Database View | 🟡 | 🟡 | ⚪ | 🟢 | 🟢 | 🟡 |
| Connections | 🟢 | 🟢 | ⚪ | 🟢 | 🟢 | 🟢 |
| Discovery | 🟢 | 🟡 | 🟢 | 🟢 | 🟡 | 🟡 |
| Masking | 🟡 | 🔴 | 🟡 | 🟢 | 🟢 | 🔴 |
| Synthetic | 🟡 | 🟡 | 🟢 | 🟢 | 🟢 | 🟡 |
| Subsetting | 🟡 | 🔴 | 🟢 | 🟢 | 🟢 | 🔴 |
| Workflows | 🟢 | 🟢 | 🔴 | 🟢 | 🟢 | 🔴 |
| Jobs | 🟢 | 🟡 | 🔴 | 🟢 | 🟢 | 🔴 |
| Compliance | 🔴 | 🟢 | 🔴 | 🟢 | 🟢 | 🔴 |
| Ephemeral | 🔴 | 🟡 | 🔴 | 🟢 | 🟢 | 🔴 |
| Settings | 🟡 | 🟡 | ⚪ | 🟡 | 🟢 | 🟡 |

**Headline metrics**: backend pytest 332/332 unit pass · 37/38 integration (1 OIDC env-config failure) · frontend `tsc --noEmit` 0 errors · Playwright 146/147 (1 real SSR regression) · 11/12 canonical API probes 200 · 12/12 frontend page probes 200.

---

## Privacy Hub
**Overall: 🔴** — UI is functional but the `apply-all` action is misleading: it creates rules without enqueueing the masking task.

### Backend (🟡 stub by design)
- Router `backend/app/api/v1/privacy_hub.py` — 2 endpoints. Auth: yes; RBAC: no; mounted at `__init__.py:43`. No domain/application layer (acceptable per Phase 49 design).
- `apply-all` writes masking rules directly via SQLAlchemy (`privacy_hub.py:296-320`), bypassing `MaskingRepository` and DDD events — provenance won't surface in masking domain events.
- Default-generator map (`privacy_hub.py:32-43`) duplicates `PII_STRATEGY_MAP` in `application/masking/handlers.py:22-33` — drift risk.
- No project-ownership check (`privacy_hub.py:218-320`) — any authenticated user can read/write any project's privacy hub.

### Frontend (🟢)
- Embedded in `frontend/src/app/projects/[projectId]/page.tsx` (49 LOC, line 41). Components: `components/privacy-hub/privacy-hub.tsx` (447 LOC), `recommended-generators-modal.tsx` (264 LOC).
- API calls: `GET /api/v1/projects/{id}`, `GET .../privacy-hub`, `POST .../privacy-hub/apply-all`. Wiring complete.
- Gaps: `privacy-hub.tsx:58-62` swallows fetch error to `setData(null)` — user can't tell whether discovery hasn't run vs. backend error. No `aria-live` on bulk-apply toast (`privacy-hub.tsx:148-153`).

### Workflow (🔴 — critical)
- **`apply-all` does NOT mask data.** It only inserts `masking_rules` rows (`privacy_hub.py:262-320`); no `run_masking_task.delay()` is ever invoked. After a successful response the UI implies "applied", but data is unchanged. Either enqueue masking for the default policy or rename to `bulk-create-rules`.

### Tests & Runtime
- `GET /api/v1/projects/{pid}/privacy-hub` → 200 (empty: `sensitive_count=0, recommendations=[]`).
- Page `/projects/{pid}` → 200 (39.9 KB body).
- E2E coverage: `dashboard.spec.ts`, `projects.spec.ts` — passing (chromium).

### Gaps & Recommendations
1. **`apply-all` is purely advisory** — enqueue `run_masking_task` after rule creation (`privacy_hub.py:296-320`).
2. **No project-ownership guard** — wrap endpoints with the same `_get_owned_project` pattern from `projects.py`.
3. **Generator map drift** — consolidate `privacy_hub.py:32-43` and `application/masking/handlers.py:22-33` into one source of truth.

---

## Database View
**Overall: 🟡** — Functional but architecturally a tight stub with scale concerns.

### Backend (🟡 stub by design)
- Router `database_view.py` — 3 endpoints. Auth: yes; RBAC: no; mounted at `__init__.py:44`. No domain/application layer.
- Cross-imports `_get_or_create_default_policy` from `privacy_hub.py` (`database_view.py:30-32`) — leaking private helper across modules.
- `list_columns` is unpaginated (`database_view.py:100-128`) — 10k+ column projects will time out.
- `GENERATOR_CHOICES` (`database_view.py:42-50`) duplicated against `ALLOWED_GENERATOR_TYPES` in `generator_presets.py`.

### Frontend (🟡)
- Page `database/page.tsx` (345 LOC, fully inline; no `components/database/`). API: `GET /database`, `POST/DELETE /columns/{col}/rule`.
- Bug: tree keyed by `schema.table` but `aside` splits on `.` and joins from index 1 (`database/page.tsx:69-80, 192-208`) — table names with dots produce wrong labels.
- No error retry button — `data === null` requires full page reload (`database/page.tsx:131`).
- 345 LOC inline violates 500-LOC trajectory guidance.

### Workflow (⚪ n/a)
- Read-only feature; no Celery dispatch (correct).

### Tests & Runtime
- `GET /api/v1/projects/{pid}/database` → 200. Page → 200 (35 KB).
- No dedicated E2E spec; covered transitively by `discovery-masking.spec.ts`.

### Gaps & Recommendations
1. **Dot-in-table-name bug** — fix tree splitting (`database/page.tsx:69-80, 192-208`).
2. **Unbounded `list_columns`** — add limit/offset pagination (`database_view.py:100-128`).
3. **De-duplicate `GENERATOR_CHOICES`** — single source from generator-presets module.

---

## Connections
**Overall: 🟢** — Fully wired across DDD layers.

### Backend (🟢)
- Router `connections.py` — 9 endpoints (CRUD + test + schema introspection). Auth: yes; RBAC: no; mounted at `__init__.py:31`.
- Full DDD: entities, events, repository, services, value objects (`ConnectorType`, `Credentials`), `schema_drift.py`.
- Fernet credential encryption via `infrastructure/security/encryption.py`. Migrations `001 / 012 / 016`.
- Concerns: `ConnectionTestService` (`services.py:13-23`) has a misleading "Phase 3" placeholder docstring; real test logic is in `TestConnectionHandler`. Preflight (`connections.py:170-194`) has 3s timeout but no rate limit — SSRF/internal-scan risk from authenticated users.

### Frontend (🟢)
- Page (83 LOC) + 6 components (`connection-card`, `connection-fieldset`, `connection-form-drawer`, `connection-list`, `connector-tile-grid`, `schema-changes-panel`). Zustand store with `testResults`, `testingIds`, `schemas`, `safe_extras` round-tripped.
- Minor: `<SchemaChangesPanel>` rendered per-connection (`connections/page.tsx:59-72`) — N panels fetching independently; no virtualization.

### Workflow (⚪ n/a)
- CRUD-only (correct).

### Tests & Runtime
- Probe 200; page 200 (36.6 KB). E2E specs: `connections.spec.ts`, `connector-auth-flows.spec.ts`, `connector-edit-preserves-secrets.spec.ts`, `connectors-9-types.spec.ts` — all passing.

### Gaps & Recommendations
1. **Preflight has no rate limit** — add a per-user throttle on `POST /connections/preflight` (`connections.py:170-194`).
2. **Remove dead docstring** in `domain/connection/services.py:13-23`.
3. **Virtualize `<SchemaChangesPanel>`** at scale (`connections/page.tsx:59-72`).

---

## Discovery
**Overall: 🟡** — Backend complete and workflow async; UI has a multi-schema blind spot.

### Backend (🟢)
- Router `discovery.py` — 5 endpoints; mounted at `__init__.py:32`. Full DDD; migrations `003 / 018 / 019`; PII detector under `infrastructure/ai/pii_detector.py`.
- Concerns: `RunDiscoveryHandler(repo, None, session)` passed at `discovery.py:81` — verify None registry is tolerated; `uuid.UUID(body.connection_id)` raises ValueError on bad input (`discovery.py:84`) instead of 422; `/discovery/pii` (`discovery.py:154-194`) doesn't verify `schema_id` belongs to `project_id`.

### Frontend (🟡)
- Full component set (8 files). Store tracks schemas/columns/relationships/piiColumns. Dynamic-imports `RelationshipGraph` (SSR off).
- Bug: PII tab fetches only `schemas[0].id` (`discovery/page.tsx:38`) — multi-schema projects can't see the rest; no UI selector.
- Bug: graph node list flattens tables without `schema_name` qualifier (`discovery/page.tsx:81`) — same-named tables across schemas collide.

### Workflow (🟢)
- Discovery → `_run_discovery_async` (`workflow_tasks.py:113-139`). Standalone async via `run_discovery_task` (`application/discovery/handlers.py:65-66`, `projects.py:187-189` for auto-discover on connection create). Status updates yes; DLQ insert no.

### Tests & Runtime
- E2E: `discovery-masking.spec.ts`, `sensitivity-rules.spec.ts` passing.
- Probes: list endpoints 422 without query params (strict-validation; not a bug, but UI must pass `connection_id`/`schema_id`).
- Page → 200 (41.2 KB).

### Gaps & Recommendations
1. **Multi-schema PII blind spot** — add schema selector in PII tab (`discovery/page.tsx:38`).
2. **Schema-collision in graph** — qualify tables by schema name (`discovery/page.tsx:81`).
3. **Cross-project schema read** — verify `schema_id` ownership in `/discovery/pii` (`discovery.py:154-194`).

---

## Masking
**Overall: 🔴** — Engine and worker fully implement linked-column joint generation, but the REST API silently strips the fields and the UI never invokes preview.

### Backend (🟡)
- Router `masking.py` — 7 endpoints; mounted at `__init__.py:34`. Application layer complete; **domain `services.py` is empty** (single docstring).
- 8 strategies in `infrastructure/engine/masking_engine.py` (HASH, REDACT, FAKER_REPLACE, NULLIFY, FPE, PARTIAL_MASK, PRESIDIO_REDACT, SHUFFLE).
- **Linked-column joint generation is fully wired in engine + worker** (`masking_engine.py:106-152`, `masking_tasks.py:34-48,165-169,286-304`) but **`RuleCreate`/`RuleUpdate` Pydantic models have no `linked_column_ids` / `consistency_group` fields** (`masking.py:28-34, 96-100`). Clients can't set them via REST — feature is dark.
- Wildcard `from .commands import *` and `from .handlers import *` (`masking.py:12-13`) — fragile.
- `update_rule` (`masking.py:103-125`) bypasses domain validation — client can PUT `{"masking_type":"nuke"}` and corrupt rows.

### Frontend (🔴)
- Page (225 LOC) + 3 components. Store actions include `previewMasking` and `executeMasking`.
- **Bug: page renders `<MaskingPreview data={previewData}/>` but never calls `previewMasking()`** (`masking/page.tsx:222`). No Preview button anywhere. Preview pane is permanently empty — dead feature surface.
- Auto-suggest calls `autoSuggest(projectId, "")` with empty `schemaId` (`masking/page.tsx:64`).
- `appliedRules` kept in component state (`masking/page.tsx:20`) — page refresh loses the "Applied" pill state.

### Workflow (🟡)
- `masking` → `run_masking_task` via `application/masking/handlers.py:95-96`. Status updates per table; no DLQ insert on retry exhaustion (`masking_tasks.py:361`). DLQ retry path requires `connection_id` in payload (`admin.py:336-340`) which is never written — structurally broken.

### Tests & Runtime
- Probe 200; page 200 (42.6 KB).
- Unit tests passing; integration `test_auto_suggest_requires_auth` has async-cleanup warning (`Connection._cancel` coroutine never awaited).
- E2E `discovery-masking.spec.ts` passes — note: would not catch the dead preview because UX never reaches it.

### Gaps & Recommendations
1. **Preview UI never fires** — add a Preview button on `masking/page.tsx` that calls `useMaskingStore.previewMasking(...)`.
2. **Expose `linked_column_ids` / `consistency_group` via REST** — add fields to `RuleCreate`/`RuleUpdate` (`masking.py:28-34, 96-100`).
3. **Validate `masking_type` enum on update** (`masking.py:103-125`).
4. **DLQ-retry payload missing** — write `connection_id` into job `payload` in `ExecuteHandler` so admin retry works.

---

## Synthetic
**Overall: 🟡** — Generation works; quality auto-load is dead due to a missing useState setter.

### Backend (🟡)
- Router `synthetic.py` — 15 endpoints across configs, preview, NLP, quality, file schemas, file output, file sets. **1034 LOC** — well past 500-LOC guideline. Should split file-schema endpoints into a dedicated router.
- Full DDD including rich `file_schema.py` (276 LOC). Engines: faker (311 LOC), llm (209), statistical (229), file-set orchestrator (179), quality evaluator (167). Parsers: copybook, excel dictionary.
- `PreviewHandler` hard-codes `schema_metadata = {"relationships": []}` (`application/synthetic/handlers.py:61`) — preview ignores discovered FKs; diverges from full generator's behavior.
- Verify `output_mode="different_connection"` has `target_connection_id` FK in migrations `017 / 020`, otherwise misroutes silently.

### Frontend (🟡)
- Page (106 LOC) + 11 components. Two stores (`synthetic-store`, `file-output-store`).
- **Bug: `const [lastConfigId] = useState<string | null>(null)`** (`synthetic/page.tsx:25`) — setter not destructured, so `<QualityReport configId={lastConfigId}/>` always receives null. Quality auto-load is dead.
- `<NLPPromptForm connectionId={selectedConnection}>` passes empty string when LLM selected without connection (`synthetic/page.tsx:84`) — should disable form until valid.

### Workflow (🟢)
- `synthetic` → `_run_generation_async` (`workflow_tasks.py:169-194`). Standalone via `run_generation_task` (`application/synthetic/handlers.py:94-95`); file sets via `run_file_set_generation_task` (`synthetic.py:995-1032`). Quality eval runs inline post-generation (`synthetic_tasks.py:96-121`). No DLQ insert.

### Tests & Runtime
- Probe 200; page 200 (42.2 KB).
- E2E `synthetic-subsetting.spec.ts` passing.
- Unit tests cover faker, profile-guided, quality evaluator, columnar/csv/fixed-width/vsam writers.

### Gaps & Recommendations
1. **`lastConfigId` dead state** — wire from store after `createConfig`, or remove (`synthetic/page.tsx:25, 99`).
2. **Split `synthetic.py`** — file-schema endpoints to `synthetic_file_schemas.py` (over 1000 LOC).
3. **Preview ignores FK relationships** — pass real `relationships` into `PreviewHandler` (`handlers.py:61`).

---

## Subsetting
**Overall: 🔴** — Backend works; UI ships a decorative-only dependency graph.

### Backend (🟡)
- Router `subsetting.py` — 5 endpoints; mounted at `__init__.py:35`. **Domain `services.py` empty**; no `value_objects.py`; no `repository.py` interface (port lives only in infrastructure — hexagonal violation).
- Application layer complete. Engine `subsetting_engine.py:128` has `TODO: Apply WHERE filter at DB level instead of fetching all` — analyzer pulls full rows before subsetting; OOM on real tables.
- Wildcard imports (`subsetting.py:12-13`).

### Frontend (🔴)
- Page (89 LOC) + 3 components.
- **Bug: page passes `relationships={[]}` and `rootTables={[]}` to `<DependencyGraph>`** (`subsetting/page.tsx:82-84`). Graph renders isolated nodes with **no edges and no root highlighting** (confirmed at `dependency-graph.tsx:71-80,101,117`).
- `traversalDirection="upstream"` hard-coded (`subsetting/page.tsx:83`) — should mirror config's strategy.
- Re-clicking a config card re-runs analysis (`subsetting/page.tsx:33`) — no memoization.

### Workflow (🟢)
- `subsetting` → `_run_async` (`workflow_tasks.py:196-221`). Standalone via `run_subsetting_task` (`application/subsetting/handlers.py:132-133`). Progress milestones 10/25/40/100. No DLQ insert.

### Tests & Runtime
- Probe 200; page 200 (53.1 KB).
- E2E `synthetic-subsetting.spec.ts` passing — does not catch the empty-graph bug because the test doesn't assert edges exist.
- Unit tests cover `subsetting_engine` and FK traversal.

### Gaps & Recommendations
1. **Wire dependency graph** — fetch from `discovery-store.relationships`, derive roots from selected config (`subsetting/page.tsx:82-84`).
2. **Push WHERE to DB** — fix engine `TODO` (`subsetting_engine.py:128`).
3. **Add domain repository port** — move interface to `domain/subsetting/repository.py` (currently only infra adapter).

---

## Workflows
**Overall: 🔴** — DAG validation and async execution work, but checkpoint/resume is write-only and scheduling is fictional.

### Backend (🟢)
- Router `workflows.py` — 5 endpoints. Full DDD; `WorkflowValidator` with topological sort + cycle detection (`domain/workflow/services.py`). Migration `008`.
- Concerns: list response omits `dag_definition` (`workflows.py:30-37`); no update/delete/pause; raw `JobModel.job_type=="workflow"` filter in router (`workflows.py:84-126`) couples to persistence model.

### Frontend (🟢)
- Page + 6 components. XYFlow v12 canvas confirmed (`workflow-canvas.tsx:15`). Node palette has **all 5 types**: discovery, masking, synthetic, subsetting, quality_check (`node-palette.tsx:7-12`). Legacy alias normalization at canvas:34-42.
- Gaps: invalid edges silently rejected (`workflow-canvas.tsx:86`) — no toast; JSON parse swallowed in code-mode (`workflow-canvas.tsx:158`).

### Workflow (🔴)
- **Checkpoint is write-only** (`workflow_tasks.py:74`). On retry, executes from `order[0]` regardless of `job.checkpoint.current_node` — no resume logic at `workflow_tasks.py:38-58`.
- **Cron scheduling is fictional**. `WorkflowModel.schedule` column exists (`models/workflow.py:19`); domain comment says "stored, not executed in v0.2" (`entities.py:31`); **no `celery_app.conf.beat_schedule`, no celery-beat worker, no scheduling daemon**.
- **`quality_check` node is a no-op** (`workflow_tasks.py:223-227`) — only logs config_id; never persists a quality report. The `export` legacy alias maps to this no-op.
- **Unknown node types are silently skipped** (`workflow_tasks.py:229-231`) — typos succeed with zero work done.
- **Node timeout not enforced** — `NODE_TIMEOUT=1800` declared (`workflow_tasks.py:16`) but never wrapped around `_execute_node`.
- **TOCTOU race on concurrency check** (`application/workflow/handlers.py:48-66`) — two concurrent executes both pass the SELECT, both `delay()`.
- **`run_workflow_task.delay()` called pre-commit** (`handlers.py:68-69`) — if commit later fails, orphan task fires.
- **Child jobs use zero-UUID `created_by`** (`workflow_tasks.py:127,156,184,210`) — FK violation if `jobs.created_by → users.id` exists.

### Tests & Runtime
- Probe 200; page 200 (36.3 KB).
- E2E `full-workflow.spec.ts`, `workflows-jobs.spec.ts` passing.

### Gaps & Recommendations
1. **Implement checkpoint resume** — read `job.checkpoint.current_node` on retry (`workflow_tasks.py:38-58`).
2. **Wire celery-beat or remove `schedule`** — current state misleads API consumers.
3. **Fail-fast on unknown node types and `quality_check` no-op** (`workflow_tasks.py:223-231`).
4. **Enforce `NODE_TIMEOUT`** via `asyncio.wait_for` (`workflow_tasks.py:70`).
5. **Fix concurrency TOCTOU** — DB unique partial index or `SELECT ... FOR UPDATE`.

---

## Jobs
**Overall: 🔴** — Read path works; the underlying DLQ and cancellation infrastructure are broken.

### Backend (🟢)
- Router `jobs.py` — 4 endpoints. Shared domain (`app/domain/shared/job.py`). `JobModel` + `DeadLetterJobModel` + repo. Migration `005`.
- Concerns: `JobDetailResponse` exposes `checkpoint` JSONB (`jobs.py:43-46`) — may leak PII / connection ids; review what workers write. No project-ownership verification in `list_jobs` (`jobs.py:55-69`).

### Frontend (🟡)
- Page (122 LOC) + 5 components. 10s polling.
- **Bug: `<JobGantt jobs={useJobStore.getState().jobs}/>`** (`jobs/page.tsx:117`) — `getState()` bypasses subscription; Gantt won't re-render on poll. Switch to `useJobStore((s) => s.jobs)`.
- Polling continues during filter changes (`jobs/page.tsx:31-35`) — race; consider `AbortController`.

### Workflow (🔴)
- **`celery_task_id` column is never populated** by any worker — Cancel-by-Celery-ID is impossible. Worker keeps running after a "cancel" DB update.
- **Domain `JobType` enum lacks `WORKFLOW`, `FILE_SET`, `COMPLIANCE`, `EPHEMERAL`** (`domain/shared/job.py:21-26`). Workers persist raw `job_type="workflow"` strings; `_job_response` calls `.value` (`api/v1/jobs.py:123`) — throws `ValueError` for any workflow job detail view.
- **DLQ table is dead** — `DeadLetterJobModel` exists with admin list/resolve/retry endpoints (`admin.py:210-361`), but **nothing writes to it**. All four task files call `task.retry(exc=exc)` and don't handle `MaxRetriesExceededError`. Admin UI operates against an empty table.
- DLQ retry for masking expects `connection_id` in payload (`admin.py:336`) which is never written — structurally broken.
- SSE endpoint **polls DB every 2s** despite an inline comment claiming Redis pub/sub (`events.py:80, 91, 98-114`).

### Tests & Runtime
- Probe 200; page 200 (39.5 KB).
- E2E `workflows-jobs.spec.ts`, `user-journeys.spec.ts` passing.

### Gaps & Recommendations
1. **Wire `celery_task_id`** in every `_run_*_async` from `task.request.id` before first commit.
2. **Extend `JobType` enum** to include all real values; fix `_job_response` to handle unknowns gracefully.
3. **Populate DLQ on retry exhaustion** — add `celery.signals.task_failure` handler in `celery_app.py` that inserts `DeadLetterJobModel` when `task.request.retries >= task.max_retries`.
4. **Replace SSE polling with Redis pub/sub** as the inline comment promises (`events.py:80`).

---

## Compliance
**Overall: 🔴 (critical "looks complete but isn't")** — Reports generate successfully and return PDFs, but every report contains zero data.

### Backend (🔴)
- Router `compliance.py` — 3 endpoints; mounted at `__init__.py:37`.
- Reporter classes are real: `hipaa_reporter.py` (58), `gdpr_reporter.py` (49), `ccpa_reporter.py` (60), `pdf_generator.py` (81), `LocalFilesystemStorage`. Migration `009`.
- **Critical: `GenerateReportHandler.handle` passes hard-coded empty data** (`application/compliance/handlers.py:41-43`): `pii_columns: list[dict] = []; masking_rules: list[dict] = []; project_info = {"project_id": ..., "connections": []}`. Every report — regardless of project state — has zero PII findings and zero rules.
- Constructor accepts `discovery_repo` and `masking_repo` but the handler body never uses them (`compliance.py:47` passes `None`).
- Stale narrative: `HIPAAReporter.generate` says "Detailed RBAC enforcement pending Phase 18 implementation" (`hipaa_reporter.py:33`) — RBAC IS implemented (`infrastructure/auth/rbac.py`).
- Domain `services.py` empty.

### Frontend (🟢)
- Page (26 LOC) + 2 components. Store + `generateReport` action. Thin but functional.

### Workflow (🔴)
- **Compliance is fully sync** — runs inside the FastAPI request (`compliance.py:48-50`). No `compliance_tasks.py`. Large project reports will hit gateway timeout. No progress tracking.

### Tests & Runtime
- Probe 200; page 200 (38.7 KB).
- No dedicated E2E spec; covered tangentially by `assistant-notifications.spec.ts`.

### Gaps & Recommendations
1. **Populate report data** — wire `discovery_repo.list_pii_columns()` and `masking_repo.list_rules()` into the handler (`application/compliance/handlers.py:41-43`).
2. **Move generation off the request thread** — create `compliance_tasks.py::run_report_generation` Celery task; return 202 + job_id.
3. **Refresh reporter narrative** (`hipaa_reporter.py:33`) to reflect shipped RBAC.

---

## Ephemeral
**Overall: 🔴** — UI is polished but the underlying environment provisioner doesn't exist. Rows live forever in `pending`.

### Backend (🔴)
- Router `ephemeral.py` — 3 endpoints. Migration `021_ephemeral_environments.py` ships, model exists. Router docstring (`ephemeral.py:1-16`) **explicitly notes the data-copy controller is a deferred follow-up**.
- New rows persist as `status="pending"` (`ephemeral.py:201-205`) and never transition — no controller to flip `pending → provisioning → ready`.
- Lazy `_maybe_flip_expired` does a write inside list/create endpoints (`ephemeral.py:127-146`) — race-prone, fails on read-only sessions.
- No POST to refresh / extend TTL — common workflow not supported.

### Frontend (🟡)
- Page (**542 LOC**, fully inline — exceeds project's 500-LOC rule). Provision dialog (310-443), revoke dialog (447-512), countdown timer with adaptive interval (86-103).
- No `source_job_id` field even though type expects it (`ephemeral/page.tsx:36, 334`).
- `err.message` referenced on potentially non-Error rejection (`ephemeral/page.tsx:71`).

### Workflow (🔴)
- **No Celery task file** — no async provisioning. TTL sweep is manual `DELETE`.

### Tests & Runtime
- Probe 200; page 200 (37 KB). No dedicated E2E spec.

### Gaps & Recommendations
1. **Either ship the data-copy controller or label the feature alpha** in the UI — current state is misleading.
2. **Extract dialogs and rows** to `components/ephemeral/` (542 LOC → <500).
3. **Move TTL flip out of GET handlers** — background task or scheduled job.

---

## Workflows feature note: see Workflows section above for full coverage.

---

## Compliance feature note: see Compliance section above for full coverage.

---

## Settings
**Overall: 🟡** — No dedicated module by design; per-project settings are an open JSONB bucket and source/destination sections are link placeholders.

### Backend (🟡 by composition)
- No dedicated router. Settings surface is split across:
  - `admin.py` — LLM provider config (`/admin/settings/llm` lines 389-436), audit logs, member mgmt, DLQ, encryption-key rotation. Admin-only via `require_admin`.
  - `projects.py` — `settings: dict | None` JSONB field on project entity (lines 47, 57, 277).
  - `webhooks.py` — webhook CRUD (admin-only).
- LLM settings stored in file-backed `infrastructure/ai/llm_settings.py`, not the DB — no audit-log on PUT, no migration, no domain entity, no concurrency safety.
- `ProjectModel.settings` (`projects.py:277-278`) is an unschematized dict — clients can stash anything including secrets.
- No tenant/org-level settings — `MAX_TTL_DAYS = 30` and similar constants should be tenant-settable.

### Frontend (🟡)
- Page (339 LOC, inline). Sections: Details, Source Settings, Destination Settings, Webhooks.
- **"Source settings" and "Destination settings" are just deep-links to Connections** (`settings/page.tsx:157-204`). Labels imply more than they deliver — rename to "Quick links" or add real content.
- Webhook secret truncated to 12 chars in toast (`settings/page.tsx:240-241`) — full value in response is lost; show in copy-to-clipboard banner.
- Webhook POST only sends `{url}` (`settings/page.tsx:236`) — no event filter selection.

### Workflow (⚪ n/a)
- CRUD-only.

### Tests & Runtime
- E2E `admin.spec.ts` passes.
- Integration `test_login_redirects_to_oidc` **fails** (`tests/integration/test_auth_flow.py:18`) — `GET /api/v1/auth/sso/login` returned 503 (no OIDC provider env). Treat as env-config rather than code bug; either supply dev OIDC config or accept 503 when SSO is disabled.
- Page `/projects/{pid}/settings` → 200 (40.4 KB). Top-level `/settings` returns 404 by design (no global settings route).

### Gaps & Recommendations
1. **Add LLM-settings concurrency + audit** — move to DB-backed or wrap in a lock; emit audit-log entries on PUT.
2. **Validate `ProjectModel.settings` payload** — define a schema instead of free-form dict.
3. **Make "Source/Destination settings" sections do something**, or rename to "Quick links".
4. **Fix or skip OIDC test** when SSO env is absent (`test_auth_flow.py:18`).

---

## Cross-Cutting Findings

### Architecture
- **Stubs without DDD layers** (deliberate per Phase 49/50): Privacy Hub, Database View, Ephemeral. Acceptable as aggregators, but several leak private helpers across modules (`database_view.py:30-32` imports `_get_or_create_default_policy` from `privacy_hub.py`).
- **Settings has no dedicated module** — surface split across admin/projects/webhooks; per-project settings is an open JSONB dict.
- **Hexagonal-architecture violations**: Subsetting has no domain `repository.py` interface; handlers import the infra adapter directly. Workflows list endpoint queries `JobModel.job_type=="workflow"` raw instead of via a job repository method.
- **Wildcard imports** in `masking.py:12-13` and `subsetting.py:12-13` — fragile on rename.
- **`synthetic.py` is 1034 LOC**, `ephemeral/page.tsx` is 542 LOC — both exceed CLAUDE.md's 500-LOC rule.
- **Empty domain `services.py`** files (single docstring): masking, subsetting, compliance.

### RBAC / Authorization
- **`require_admin` is used only in `admin.py` and `webhooks.py`.** Every other feature (Privacy Hub, Database View, Connections, Discovery, Masking, Synthetic, Subsetting, Workflows, Jobs, Compliance, Ephemeral) is identity-only.
- **Project-ownership checks are inconsistent.** `projects.py` has `_get_owned_project`; Privacy Hub, Database View, Discovery (some paths), and Jobs (`list_jobs`) rely only on `WHERE project_id = ?` without verifying user→project membership.
- `editor` / `viewer` roles exist on `MemberRepository` (`admin.py:115`) but aren't enforced anywhere downstream.
- Dev auth bypass: `GET /api/v1/projects` returns 200 without any `Authorization` header. Confirm this is a dev-only middleware before shipping.

### Workflow & Async (most systemic gaps)
- **DLQ is dead.** `DeadLetterJobModel` + admin UI + retry endpoints exist; nothing populates the table. Add a `celery.signals.task_failure` handler.
- **`celery_task_id` column is always NULL.** Job cancel cannot revoke the Celery task — workers keep running after "cancel" status update.
- **Webhook HMAC signature is broken.** `dispatcher.py:33` keys HMAC with `secret_hash` (sha256 of secret) but receivers only have the raw secret. Receivers cannot verify signatures — the whole webhook auth surface is unusable as designed.
- **Webhook retry tail dropped silently.** `asyncio.create_task` fire-and-forget inside Celery's per-task `asyncio.run` cancels pending tasks when the loop closes.
- **No `celery_app.conf.beat_schedule`** — `WorkflowModel.schedule` field is decorative.
- **Workflow checkpoint is write-only** — no resume on retry.
- **Unknown workflow node types silently skipped** — typos succeed with zero work.
- **`quality_check` and `export`-alias node** is a no-op stub.
- **`NODE_TIMEOUT` declared but never enforced.**
- **Domain `JobType` enum lacks `WORKFLOW` / `FILE_SET` / `COMPLIANCE` / `EPHEMERAL`** — workflow job detail responses throw `ValueError`.
- **TOCTOU race on workflow concurrency check.**
- **Privacy Hub `apply-all` doesn't actually mask data.**
- **Compliance generation is sync — empty data — stale narrative.**
- **SSE uses DB polling, not Redis pub/sub** despite inline comment.

### Deferred work (from `.paul/STATE.md` + RELEASE-NOTES-v0.8.md)
- **Linked-column joint masking generation** — engine + worker fully wired (`019_linked_columns.py`); REST API silently strips the fields. UI surface absent.
- output_mode UI polish (Phase 55).
- Virtual FK toggling on relationship graph (UI deferred).
- Schema-changes panel on connection detail UI (backend ready, UI deferred).

### Tests & Tooling
- **Real Playwright regression**: `accessibility.spec.ts:17` — navigating to `/projects` throws Next.js SSR `TypeError: Cannot read properties of null (reading 'useContext')`. Likely a client-only Provider imported into a server component, or duplicate React versions. Check recent changes under `frontend/src/app/projects/`.
- Backend 332/332 unit pass · 37/38 integration (1 OIDC env failure).
- `RuntimeWarning: coroutine 'Connection._cancel' was never awaited` in `test_masking_api.py::test_auto_suggest_requires_auth`.
- Tooling drift: docs reference `pnpm`; repo ships `package-lock.json`; `playwright.config.ts` uses `npm run dev`. Pick one.
- Backend has no pinned pytest deps — Python 3.13 + system `pytest 7.4.4` + `pytest-asyncio 1.3.0` triggers `ImportError: cannot import name 'FixtureDef'`. Pin in `pyproject.toml`.

---

## Top 10 Actionable Gaps (priority order)

1. **🔴 Compliance reports are empty.** `application/compliance/handlers.py:41-43` hard-codes `pii_columns=[]`, `masking_rules=[]`. Every PDF ships with zero findings. **This is the highest-severity "looks complete but isn't" issue in the codebase.**
2. **🔴 Privacy Hub `apply-all` doesn't actually mask data.** `privacy_hub.py:262-320` creates rules but never enqueues `run_masking_task`. Users see "applied" but data is unchanged.
3. **🔴 Masking preview UI is dead.** `masking/page.tsx:222` renders `<MaskingPreview>` but the page never calls `previewMasking()` — no button anywhere.
4. **🔴 Subsetting dependency graph is decorative.** `subsetting/page.tsx:82-84` passes empty `relationships` and `rootTables` — graph renders isolated nodes.
5. **🔴 Linked-column masking is dark.** Engine + worker fully implemented; REST `RuleCreate`/`RuleUpdate` strips `linked_column_ids` / `consistency_group`. The shipped feature is unreachable from clients.
6. **🔴 DLQ table is never populated.** Admin UI operates against an empty table; retry exhaustion silently drops jobs (`celery_app.py` lacks `task_failure` signal handler).
7. **🔴 Webhook HMAC signatures unverifiable.** `dispatcher.py:33` keys HMAC with `secret_hash`, but receivers have the raw secret. Webhook auth is unusable as designed.
8. **🔴 Frontend SSR regression on `/projects`.** `TypeError: Cannot read properties of null (reading 'useContext')` — caught by Playwright; will hit real users on the projects-list route.
9. **🔴 Ephemeral provisioner does not exist.** Rows persist in `pending` forever. UI implies functionality; backend ships a deferral docstring.
10. **🟡 Workflow checkpoint is write-only / cron scheduling is fictional / `celery_task_id` always NULL.** Together these mean: retries restart from node 0, `WorkflowModel.schedule` does nothing, and "cancel" never revokes the Celery task.

---

*Generated by 4-agent evaluation swarm — backend-evaluator, frontend-evaluator, workflow-evaluator, tester — aggregated by lead. Static audit + live-stack probes against backend :8000 and frontend :3000. Report only; no code changes were made.*
