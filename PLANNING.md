# DataWrangler — Build Plan

> Sprint-level build plan for the DataWrangler TDM platform. 13 sprints across 26 weeks (3 phases). Team size: 4+ developers.

---

## Team Roles (Suggested)

| Role | Focus |
|------|-------|
| **Backend Lead** | DDD domain layer, FastAPI API, Celery workers, DI container |
| **Data Engineer** | Connectors, synthetic engines (Faker/Statistical/LLM), masking engine, subsetting |
| **Frontend Lead** | Next.js app, Ant Design UI, ReactFlow workflow builder, Playwright E2E |
| **Platform/DevOps** | Docker, SSO auth, storage backends, monitoring, CI/CD, production deployment |

---

## Phase 1: MVP (10 weeks)

### Sprint 1-2 (Weeks 1-4): Foundation

#### Backend Lead
- [ ] Initialize FastAPI project with DDD folder structure (`domain/`, `application/`, `infrastructure/`, `api/`)
- [ ] Implement `domain/shared/` base classes: Entity, AggregateRoot, ValueObject, DomainEvent, Repository ABC
- [ ] Implement `domain/connection/` bounded context: entities, value objects, repository ABC, services
- [ ] Set up `dependency-injector` container (`app/container.py`)
- [ ] Implement `application/connection/` commands, queries, handlers
- [ ] Implement `api/v1/projects.py` and `api/v1/connections.py` endpoints
- [ ] Set up Pydantic Settings config (`app/config.py`)
- [ ] Set up Alembic migrations with initial schema (users, projects, connections)

#### Data Engineer
- [ ] Implement `infrastructure/connectors/base.py` — `BaseConnector` ABC
- [ ] Implement `infrastructure/connectors/registry.py` — connector factory with entry-point discovery
- [ ] Implement `infrastructure/connectors/sql/postgresql.py` — full PostgreSQL connector
- [ ] Implement `infrastructure/ai/llm_provider.py` — `LLMProvider` ABC
- [ ] Implement `infrastructure/ai/claude_provider.py` — Claude API integration
- [ ] Implement `infrastructure/ai/ollama_provider.py` — Ollama self-hosted integration
- [ ] Implement `infrastructure/ai/config.py` — provider selection, fallback chain, token cost tracking

#### Frontend Lead
- [ ] Initialize Next.js 14 project with App Router + Tailwind CSS + shadcn/ui
- [ ] Set up hybrid design system:
  - [ ] Configure Tailwind with Ameritas CSS variable tokens (light + dark + system themes)
  - [ ] Install shadcn/ui base components (Button, Card, Dialog, Drawer, Input, Select, Tabs, Tooltip, etc.)
  - [ ] Install Ant Design v5 with CSS Module scoping for Table, Tree components only
  - [ ] Sync Ant Design theme tokens to CSS variables for consistent theming
  - [ ] Install 21st.dev components: "Dashboard with Collapsible Sidebar", Command Palette, AI Chat
- [ ] Install and configure Inter + JetBrains Mono fonts
- [ ] Build theme system: ThemeProvider with Light/Dark/System toggle, localStorage persistence, `prefers-color-scheme` detection
- [ ] Build `AppShell` layout: collapsible Sidebar (240px/64px) from 21st.dev, Header (56px, logo + Cmd+K search + theme toggle + notification bell + user avatar), content area (max-width 1440px)
- [ ] Build responsive sidebar: drawer mode on mobile/tablet, icon-only collapse on desktop
- [ ] Build Command Palette (Cmd+K): global search across projects, tables, columns, jobs — 21st.dev component
- [ ] Build breadcrumb navigation component
- [ ] Build SSO login page with branded design and error states
- [ ] Set up Zustand stores (projectStore, authStore, jobStore, notificationStore, themeStore)
- [ ] Build `useApi` hook with JWT token management and error handling
- [ ] Build common components: StatusBadge, ConfirmModal (typed confirmation for destructive actions), EmptyState (with illustrations + CTAs)
- [ ] Build skeleton loading components for each page layout
- [ ] Build Notification Center: bell icon dropdown, unread count badge, notification list with actions, multi-channel preferences (in-app/email/Slack)
- [ ] Implement keyboard shortcuts framework (Cmd+K search, Cmd+N new, Cmd+S save, Escape close, ? help)
- [ ] Scaffold AI Assistant sidebar: resizable right panel using 21st.dev AI Chat component, collapsible to icon
- [ ] Set up Jest + React Testing Library
- [ ] Set up Playwright with basic smoke test
- [ ] Set up WCAG 2.1 AA accessibility: focus trapping, ARIA labels, keyboard navigation, color-independent indicators

#### Platform/DevOps
- [ ] Create `docker-compose.dev.yml` with postgres, redis, backend, worker, frontend, flower
- [ ] Create `Dockerfile` for backend (Python, uvicorn)
- [ ] Create `Dockerfile` for frontend (Node, Next.js)
- [ ] Create `.env.example` with all configuration variables
- [ ] Create `Makefile` with `dev`, `test`, `lint`, `migrate` targets
- [ ] Implement SSO auth: `infrastructure/auth/oidc.py` (OIDC provider integration)
- [ ] Implement SSO auth: `infrastructure/auth/saml.py` (SAML 2.0 provider integration)
- [ ] Implement `infrastructure/auth/jwt.py` — JWT for service accounts
- [ ] Set up `api/v1/auth.py` endpoints (SSO login, callback, token refresh)
- [ ] Set up pytest + pytest-asyncio + testcontainers + factory_boy in `tests/conftest.py`
- [ ] Implement `infrastructure/monitoring/health.py` — `/health` and `/ready` endpoints
- [ ] Configure structlog for JSON logging

**Sprint 1-2 Deliverables**: Running Docker dev environment, SSO auth working, PostgreSQL connector operational, project/connection CRUD API, test infrastructure ready, LLM provider abstraction with Claude + Ollama support.

---

### Sprint 3-4 (Weeks 5-8): Discovery + PII + Faker + Frontend Core

#### Backend Lead
- [ ] Implement `domain/discovery/` bounded context: Schema, Table, Column, Relationship entities; PIIType, PIIConfidence value objects; repository ABC; events
- [ ] Implement `application/discovery/` commands (RunDiscovery, OverridePIIClassification) and query handlers
- [ ] Implement `api/v1/discovery.py` endpoints
- [ ] Implement `domain/synthetic/` bounded context: SyntheticConfig, GenerationPlan entities; BaseSyntheticEngine ABC
- [ ] Implement `application/synthetic/` commands and query handlers
- [ ] Implement `api/v1/synthetic.py` endpoints
- [ ] Implement domain event dispatcher (`infrastructure/messaging/event_bus.py`)
- [ ] Wire DiscoveryCompleted event → auto-suggest masking rules

#### Data Engineer
- [ ] Implement `domain/discovery/services.py` — `SchemaDiscoveryService` (schema introspection, column stats)
- [ ] Implement `domain/discovery/services.py` — `PIIDetectionService` (4-layer pipeline)
  - [ ] Layer 1: Regex patterns (SSN, credit card, phone, email, IP)
  - [ ] Layer 2: Presidio + spaCy NER integration
  - [ ] Layer 3: Column name heuristics
  - [ ] Layer 4: LLM classification (via LLMProvider, only when confidence < 0.4)
  - [ ] Weighted confidence scoring with thresholds
- [ ] Implement `domain/synthetic/services.py` — `FakerEngine` (PII-type-aware providers, constraint handling, FK ordering via topological sort)
- [ ] Implement `infrastructure/connectors/sql/mysql.py` — MySQL connector
- [ ] Add Alembic migrations for discovery + synthetic tables

#### Frontend Lead
- [ ] Build Project List page (`/projects`): table view + card view toggle, filters (owner, date, PII status), sort, real-time search, empty state with "Create your first project" CTA
- [ ] Build Project Detail layout with sidebar sub-navigation (Connections, Discovery, Masking, Synthetic, Subsetting, Workflows, Jobs, Compliance)
- [ ] Build Connection List: cards with connector icon, connection string (masked), status dot (green/yellow/red/gray), last tested timestamp, actions
- [ ] Build Connection Form (slide-in drawer, 480px): connector type selector with icons, dynamic fields per type, credential masking with show/hide, "Test Connection" button with inline feedback, advanced options via progressive disclosure (Airbyte pattern: minimize fields, smart defaults, collapsible "Advanced" section, field-level help tooltips)
- [ ] Build Schema Explorer: split-pane layout — collapsible tree (left, Ant Design Tree CSS-scoped) with search/filter, PII dots (red/yellow), FK link icons; column detail panel (right) with 3 tabs: Settings / Sample Data / Comments (Tonic-inspired column slide-out)
- [ ] Build PII Heatmap: grid view of all tables, color intensity = PII density, unmasked count prominently shown, click to drill into table detail (Delphix DCT-inspired)
- [ ] Build PII Results Table: all PII columns with Table, Column, PII Type, Confidence, Detector, Status columns; color-coded badges; bulk classify/dismiss; CSV export
- [ ] Build PII Override dropdown with audit note field
- [ ] Build Synthetic Engine Selector: 3 cards (Faker/Statistical/LLM) with speed/accuracy descriptions
- [ ] Build NLP Prompt Input: textarea with example prompts, "Generate Plan" button, editable plan view, 10-row preview table
- [ ] Build Synthetic Config Form for Faker/Statistical engines with parameter controls
- [ ] Set up `useSSE` hook for real-time job progress with reconnection logic

#### Platform/DevOps
- [ ] Set up Celery app (`infrastructure/messaging/celery_app.py`) with retry policies
- [ ] Implement discovery Celery task with exponential backoff (3 retries, 30s/60s/120s)
- [ ] Implement synthetic generation Celery task
- [ ] Set up circuit breaker (`pybreaker`) wrapper for LLM calls
- [ ] Write unit tests for PII detection pipeline
- [ ] Write integration tests for PostgreSQL connector

**Sprint 3-4 Deliverables**: Schema discovery working end-to-end, 4-layer PII detection operational, Faker synthetic generation producing data, MySQL connector ready, frontend showing schema explorer and PII results.

---

### Sprint 5 (Weeks 9-10): Connectors + Dashboard + Storage

#### Backend Lead
- [ ] Implement `api/v1/jobs.py` endpoints (list, detail, cancel, retry, SSE stream)
- [ ] Implement `api/v1/events.py` — SSE streaming for job progress
- [ ] Add job checkpoint support for idempotent resume
- [ ] Implement dead letter queue table and `api/v1/admin.py` DLQ endpoints

#### Data Engineer
- [ ] Implement `infrastructure/connectors/nosql/mongodb.py` — MongoDB connector (document sampling, schema inference)
- [ ] Implement `infrastructure/connectors/cloud/snowflake.py` — Snowflake connector
- [ ] Implement `infrastructure/storage/base.py` — `StorageBackend` ABC
- [ ] Implement `infrastructure/storage/local.py` — local filesystem storage (default)
- [ ] Write integration tests for MongoDB and Snowflake connectors

#### Frontend Lead
- [ ] Build Dashboard page (`/`): stat cards (projects, active jobs, tables masked, jobs today) — clickable; recent project cards with hover elevation and PII coverage %; active jobs list with real-time SSE progress bars; PII coverage donut chart
- [ ] Build Job List page (`/projects/{id}/jobs`): filterable table (type, status, date), status icons (checkmark/spinner/pending/failed), click to expand detail
- [ ] Build Job Detail view: per-table progress breakdown, real-time progress bar via SSE, auto-scrolling log viewer with level filtering (INFO/WARN/ERROR) and search, Cancel and "Retry from checkpoint" buttons
- [ ] Build Job Timeline / Gantt View: alternative to list view, shows temporal overlap and dependencies, toggle between List/Gantt, zoomable time scale (Tonic-inspired)
- [ ] Build Log Viewer component: virtualized list for performance, syntax highlighting, auto-scroll with manual override
- [ ] Build Guided Onboarding Wizard: 5-step flow (Create Project → Add Connection → Run Discovery → Review PII → Apply Masking), contextual highlights, skippable, resumable checklist in sidebar, "don't show again" preference (Tonic/Airbyte-inspired)
- [ ] Polish all empty states with illustrations, descriptions, and CTAs
- [ ] Polish all error states: form validation inline, API error modals with suggested actions, React error boundaries
- [ ] Implement optimistic updates for quick actions (toggle, delete)
- [ ] Responsive testing and fixes for tablet breakpoint
- [ ] Write Playwright E2E: create project → add connection → test connection → run discovery → view PII results → override classification

#### Platform/DevOps
- [ ] Set up Prometheus metrics endpoint (`infrastructure/monitoring/metrics.py`)
- [ ] Add request latency, job duration, and queue depth metrics
- [ ] Write integration tests for SSO auth flow
- [ ] Performance test: discovery on 100+ table schema
- [ ] Document `.env` variables and Docker setup in `docs/getting-started.md`

**Sprint 5 Deliverables**: MongoDB + Snowflake connectors operational, dashboard with real-time job monitoring, storage abstraction with local FS, DLQ for failed jobs, Prometheus metrics, E2E test covering core workflow.

---

## Phase 2: Advanced Features (8 weeks)

### Sprint 6-7 (Weeks 11-14): Statistical Engine + LLM Engine + Masking

#### Backend Lead
- [ ] Implement `domain/masking/` bounded context: MaskingPolicy, MaskingRule entities; MaskingStrategy value objects; repository ABC; events
- [ ] Implement `application/masking/` commands (CreatePolicy, AddRule, PreviewMask, ExecuteMask) and handlers
- [ ] Implement `api/v1/masking.py` endpoints
- [ ] Implement quality evaluation endpoint (`api/v1/synthetic.py` — GET quality score)
- [ ] Add Alembic migrations for masking tables

#### Data Engineer
- [ ] Implement `domain/synthetic/services.py` — `StatisticalEngine`
  - [ ] GaussianCopula synthesis using `copulas` library directly
  - [ ] CTGAN synthesis using `ctgan` library directly
  - [ ] Multi-table synthesis with HMA-inspired hierarchical approach
  - [ ] Metadata auto-detection (column types, distributions)
  - [ ] Constraint enforcement (Range, Inequality, FixedCombinations)
- [ ] Implement `domain/synthetic/services.py` — `LLMEngine`
  - [ ] NLP prompt parsing → structured generation plan
  - [ ] Plan → column-level Faker/constraint config
  - [ ] Execution with progress tracking
  - [ ] Cost tracking (token counts)
- [ ] Implement quality evaluation: KS test, column shape metrics, column pair metrics (using scipy.stats)
- [ ] Implement `domain/masking/services.py` — `MaskingEngine`
  - [ ] Strategy implementations: hash, redact, faker_replace, shuffle, nullify
  - [ ] Format-preserving encryption (FF1/FF3-1)
  - [ ] Deterministic masking (HMAC-SHA256 with project salt)
  - [ ] Chunked parallel processing (10K row batches via Celery)
  - [ ] Referential integrity across chunks

#### Frontend Lead
- [ ] Build Masking Policy List page: policy cards with name, description, rule count, last applied, default badge
- [ ] Build Masking Rule Editor (drawer): visual strategy selector (6 strategy cards with icons), target column/PII type selector, preserve format + deterministic checkboxes, FPE algorithm config
- [ ] Build Side-by-Side Data Preview: original vs transformed table with color-diff highlighting on changed values, column slide-out on header click (Settings/Sample/Comments tabs), paginated (Tonic-inspired)
- [ ] Build Masking Preview: uses Side-by-Side component, live update as config changes
- [ ] Build Statistical Engine config form: model selector (GaussianCopula, CTGAN, TVAE) with descriptions, hyperparameter controls (epochs, batch size), training time estimate display
- [ ] Build LLM Generation results: editable generation plan view with JSON editor, preview table, cost estimate (tokens), provider indicator
- [ ] Build Quality Score dashboard: overall score (0-100) gauge, per-column distribution comparison charts (histogram overlays: real vs synthetic), column pair correlation heatmap
- [ ] Build Synthetic Data preview table with virtual scrolling for large previews
- [ ] Build Quality Report dashboard (Gretel/MOSTLY AI-inspired):
  - [ ] Composite quality score gauge (0-100) with sub-metrics breakdown (Column Shapes, Column Pairs, Coverage, Boundaries)
  - [ ] Overlaid distribution charts: real (dark) vs synthetic (colored) histogram per column with match percentage
  - [ ] Correlation heatmap triplets: Original / Synthetic / Difference side-by-side with hover values
  - [ ] Privacy metrics: DCR, NNDR, identical matches count
  - [ ] Per-column drill-down on click
  - [ ] Download report as PDF / share link
- [ ] Build Dual-Mode interface for masking rules: Visual form editor ↔ JSON/YAML code editor, bidirectional sync, toggle switch (Airbyte-inspired)

#### Platform/DevOps
- [ ] Implement masking Celery task with 2-retry idempotent policy
- [ ] Implement LLM generation Celery task with 5-retry jitter policy
- [ ] Performance test: masking 1M rows across 10 tables
- [ ] Performance test: CTGAN training on 100K row table
- [ ] Write unit tests for all masking strategies
- [ ] Write integration tests for statistical engine

**Sprint 6-7 Deliverables**: Statistical synthetic engine producing distribution-preserving data, LLM engine handling NLP prompts, masking engine with all 7 strategies + FPE, quality evaluation scoring, masking UI with preview.

---

### Sprint 8-9 (Weeks 15-18): Subsetting + Workflow Builder

#### Backend Lead
- [ ] Implement `domain/subsetting/` bounded context: SubsetConfig, DependencyGraph entities; services; events
- [ ] Implement `application/subsetting/` commands (CreateConfig, Analyze, Execute) and handlers
- [ ] Implement `api/v1/subsetting.py` endpoints
- [ ] Implement `domain/workflow/` bounded context: Workflow, WorkflowNode, WorkflowEdge entities; WorkflowExecutor service; events
- [ ] Implement `application/workflow/` commands and handlers
- [ ] Implement `api/v1/workflows.py` endpoints
- [ ] Add Alembic migrations for subsetting + workflow tables

#### Data Engineer
- [ ] Implement `domain/subsetting/services.py` — `SubsettingEngine`
  - [ ] FK dependency graph builder from discovered relationships
  - [ ] Upstream (child→parent) and downstream (parent→child) traversal
  - [ ] WHERE filter application on root tables
  - [ ] Dry-run analysis (row counts per table)
  - [ ] Target by percentage or absolute row count
- [ ] Implement relationship inference improvements
  - [ ] Naming convention matching
  - [ ] Value overlap analysis (Jaccard similarity)
  - [ ] LLM-assisted inference for complex schemas
- [ ] Implement `domain/workflow/services.py` — `WorkflowExecutor`
  - [ ] DAG validation (cycle detection)
  - [ ] Topological execution order
  - [ ] Per-node Celery task dispatch
  - [ ] Node-level status tracking

#### Frontend Lead
- [ ] Build ReactFlow Workflow Canvas:
  - [ ] Custom node components: Discover (blue), Mask (orange), Generate (green), Subset (purple), Export (gray) — each with icon, title, status indicator
  - [ ] Node Palette (left panel): drag nodes onto canvas
  - [ ] Edge connections with validation: prevent invalid connections (e.g., Export before Discover), animated edges during execution
  - [ ] Per-node configuration panel (bottom drawer): context-sensitive form based on node type
  - [ ] Real-time execution status: gray (pending), blue animated (running), green checkmark (done), red X (failed)
  - [ ] Workflow toolbar: zoom controls, fit-to-screen, minimap toggle, undo/redo
- [ ] Build Workflow Run History: expandable rows with per-node timing breakdown, error details for failed nodes
- [ ] Build Workflow List page: workflow cards with name, schedule (cron readable), last run status, enable/disable toggle
- [ ] Build Relationship Graph visualization: ReactFlow or D3 — zoomable, pannable, nodes = tables (sized by row count), edges = FK relationships, click node to see columns
- [ ] Build Subsetting Config page: root table dropdown, traversal direction toggle (upstream/downstream) with visual arrow change on graph, WHERE filter input with SQL syntax highlighting, target percentage/row count input
- [ ] Build Subsetting Dry-Run view: interactive dependency graph with row counts on nodes, table breakdown grid (full count, subset count, %), total row count summary
- [ ] Build Dual-Mode for workflow: ReactFlow visual builder ↔ JSON DAG definition, bidirectional sync, export/import for CI/CD
- [ ] Build Dual-Mode for subsetting: form-based filter builder ↔ raw SQL WHERE clause with syntax highlighting
- [ ] Integrate AI Assistant with workflow + subsetting: "Build a workflow that discovers, masks PII, and generates 10K synthetic rows" → auto-creates workflow DAG
- [ ] Build inline collaboration: comment threads on workflow nodes, @mentions with notification triggers
- [ ] Write Playwright E2E: create workflow → drag 3 nodes → connect edges → configure each → execute → monitor per-node progress → view run history

#### Platform/DevOps
- [ ] Implement workflow Celery task (DAG runner with per-node dispatch)
- [ ] Implement cron scheduler for workflow scheduling
- [ ] Performance test: subsetting from 50-table schema
- [ ] Write integration tests for subsetting engine
- [ ] Write integration tests for workflow execution

**Sprint 8-9 Deliverables**: Graph-aware subsetting with dry-run analysis, ReactFlow visual workflow builder, workflow execution with per-node status, relationship graph visualization, cron-scheduled workflows.

---

## Phase 3: Enterprise (8 weeks)

### Sprint 10-11 (Weeks 19-22): Compliance + RBAC + Audit

#### Backend Lead
- [ ] Implement `domain/compliance/` bounded context: ComplianceReport, AuditEntry entities; per-regulation reporter services
- [ ] Implement `application/compliance/` commands (GenerateReport) and query handlers
- [ ] Implement `api/v1/compliance.py` endpoints (generate, list, download)
- [ ] Implement RBAC middleware: admin/editor/viewer per project
- [ ] Add RBAC checks to all existing endpoints
- [ ] Ensure all API calls create audit_log entries

#### Data Engineer
- [ ] Implement `domain/compliance/services.py` — `HIPAAReporter`
  - [ ] PHI inventory report
  - [ ] Access controls summary
  - [ ] Encryption status audit
  - [ ] BAA tracking
- [ ] Implement `domain/compliance/services.py` — `GDPRReporter`
  - [ ] Data mapping report
  - [ ] Lawful basis documentation
  - [ ] DPIA (Data Protection Impact Assessment)
  - [ ] Right-to-erasure support documentation
- [ ] Implement `domain/compliance/services.py` — `CCPAReporter`
  - [ ] Consumer data categories inventory
  - [ ] Sale/sharing tracking
  - [ ] Opt-out support documentation
- [ ] PDF report generation (via reportlab or weasyprint)

#### Frontend Lead
- [ ] Build Compliance Report generation form: regulation selector (HIPAA/GDPR/CCPA) with description of what each includes, date range picker, scope selector (all tables or specific), generate button with progress
- [ ] Build Compliance Report list: table with name, regulation badge, generated date, generated by, file size, download button, in-browser PDF preview (click to open)
- [ ] Build PII Coverage Dashboard: overall donut chart (detected/masked/pending), per-table heatmap grid (rows = tables, color intensity = PII density), click table to drill into column-level detail
- [ ] Build Audit Trail viewer: filterable table (user, action type, resource, date range), expandable rows with full detail JSON, CSV export
- [ ] Build RBAC management UI: project settings tab, user list with role dropdown (admin/editor/viewer), invite user form, role permission explanation
- [ ] Build Admin panel (`/admin`):
  - [ ] System Health: service status cards (PostgreSQL, Redis, Celery workers, LLM providers) with uptime and connection status
  - [ ] Dead Letter Queue: list of failed jobs with error details, retry and dismiss buttons, bulk actions
  - [ ] Encryption Key Rotation: one-click button with confirmation modal, progress indicator, success/failure toast
  - [ ] User Management: user list, SSO status, last login, role assignment
  - [ ] Audit Log: global filterable log (all projects)
- [ ] Build Project Activity Feed: per-project stream showing who did what and when, with inline navigation to referenced assets
- [ ] Build inline collaboration for compliance: auditor-facing annotations on compliance report items, exportable with the report

#### Platform/DevOps
- [ ] Implement audit trail middleware (log every API call)
- [ ] Implement RBAC database model and migration
- [ ] Set up PostgreSQL pg_dump backup schedule
- [ ] Write unit tests for all compliance reporters
- [ ] Write E2E test: generate compliance report → download PDF → verify content
- [ ] Security audit: CORS config, rate limiting, input validation review

**Sprint 10-11 Deliverables**: HIPAA/GDPR/CCPA compliance report generation, RBAC with project-level roles, complete audit trail, PII coverage dashboard, admin panel.

---

### Sprint 12-13 (Weeks 23-26): CLI + Production + Remaining Connectors

#### Backend Lead
- [ ] Implement API key authentication for CI/CD integration
- [ ] Implement webhook system (job completion/failure notifications)
- [ ] Implement `POST /admin/rotate-encryption-key` — re-encrypt all credentials
- [ ] API documentation review and OpenAPI spec cleanup

#### Data Engineer
- [ ] Implement remaining connectors (as capacity allows):
  - [ ] `infrastructure/connectors/sql/oracle.py`
  - [ ] `infrastructure/connectors/sql/sqlserver.py`
  - [ ] `infrastructure/connectors/file/csv.py`
  - [ ] `infrastructure/connectors/file/json_handler.py`
  - [ ] `infrastructure/connectors/file/parquet.py`
  - [ ] `infrastructure/connectors/file/avro.py`
- [ ] Implement `infrastructure/storage/s3.py` — S3-compatible storage backend
- [ ] Implement `infrastructure/storage/database.py` — PostgreSQL BLOB storage

#### Frontend Lead
- [ ] Polish all UI components for production readiness: consistent spacing, loading states, error boundaries, transitions/animations
- [ ] Build onboarding wizard for new users: 4-step flow (create project → add connection → run discovery → view results) with progress indicator, skip option, "don't show again" preference
- [ ] Build global search (Cmd+K): search projects, connections, tables, columns, jobs — with recent searches and keyboard navigation
- [ ] Build dark mode support (optional, if time permits): Ant Design theme token switching
- [ ] Accessibility audit and fixes: WCAG 2.1 AA — keyboard navigation on all interactive elements, screen reader testing (VoiceOver), color contrast verification, focus indicators
- [ ] Performance optimization: React.memo on heavy components, virtual scrolling on all large tables, code splitting per route, image/SVG optimization
- [ ] Final Playwright E2E suite: 8+ test scenarios covering all major workflows (project CRUD, connection management, discovery + PII, masking, synthetic generation, subsetting, workflow builder, compliance reports)
- [ ] Cross-browser testing: Chrome, Firefox, Safari, Edge

#### Platform/DevOps
- [ ] Build CLI tool (`cli/datawrangler/cli.py`)
  - [ ] `datawrangler discover --connection <id>` — run discovery
  - [ ] `datawrangler mask --policy <id>` — run masking
  - [ ] `datawrangler generate --config <id>` — run generation
  - [ ] `datawrangler subset --config <id>` — run subsetting
  - [ ] `datawrangler workflow run --id <id>` — execute workflow
  - [ ] `datawrangler status --job <id>` — check job status
- [ ] Create `docker-compose.prod.yml` with Nginx, resource limits, restart policies, external volumes
- [ ] Create `.env.prod` template
- [ ] Production readiness checklist: health checks, logging, metrics, backups, SSL
- [ ] Write deployment guide in `docs/`
- [ ] Load testing: full pipeline (discover → mask → generate → subset) on production-scale data

**Sprint 12-13 Deliverables**: CLI tool for CI/CD, API keys + webhooks, production Docker Compose, S3 storage option, remaining connectors, deployment documentation, production-ready platform.

---

## Dependencies Between Sprints

```
Sprint 1-2 (Foundation)
    ├── Sprint 3-4 (Discovery + PII + Faker) ── depends on connectors, DDD structure
    │   └── Sprint 5 (Connectors + Dashboard) ── depends on discovery, jobs
    │       ├── Sprint 6-7 (Statistical + LLM + Masking) ── depends on discovery results
    │       │   └── Sprint 8-9 (Subsetting + Workflows) ── depends on all engines
    │       │       └── Sprint 10-11 (Compliance + RBAC) ── depends on masking, PII
    │       │           └── Sprint 12-13 (CLI + Prod) ── depends on stable API
```

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| CTGAN training slow on large tables | High | Medium | Set row sampling limits (50K default); offer GaussianCopula as fast alternative |
| SSO integration complexity | Medium | High | Start in Sprint 1; fallback to local JWT if SSO blocks other work |
| LLM API rate limits / cost overruns | Medium | Medium | Circuit breaker + Ollama fallback + Layer 4 only when confidence < 0.4 |
| ReactFlow workflow builder complexity | Medium | High | Timebox to 2 sprints; fall back to config-based workflows if needed |
| MongoDB schema inference edge cases | Medium | Low | Document sampling with configurable depth; manual schema override |
| Snowflake connector auth complexity | Low | Medium | Use snowflake-connector-python; test with Ameritas Snowflake instance early |
| Compliance report requirements unclear | Medium | Medium | Get legal/compliance team review before Sprint 10 |

---

## Definition of Done (per Sprint)

- [ ] All sprint tasks completed
- [ ] Unit tests passing (coverage >= target)
- [ ] Integration tests passing for new features
- [ ] No P0/P1 bugs open
- [ ] API documentation updated (OpenAPI)
- [ ] Docker dev environment boots cleanly
- [ ] Code reviewed and merged to main
