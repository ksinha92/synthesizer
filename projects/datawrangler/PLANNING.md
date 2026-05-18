# DataWrangler

> AI-Powered Test Data Management Platform — Ameritas' Delphix replacement

---

## Metadata

| Field | Value |
|-------|-------|
| **Type** | Application |
| **Status** | Ideation complete — ready for `/seed graduate` |
| **Target** | Internal Ameritas tool (single-tenant) |
| **Team** | 4+ developers |
| **Timeline** | 26 weeks (13 sprints, 3 phases) |
| **Deployment** | Docker Compose on VMs |

### Skill Loadout
| Tool | Purpose |
|------|---------|
| **PAUL** | Managed build orchestration — sprint execution, task tracking |
| **AEGIS** | Security audit — OWASP top 10, credential handling, PII protection |

### Quality Gates
- [ ] All bounded contexts have entities, value objects, repository ABCs, domain events
- [ ] Hybrid UI renders correctly in light + dark + system modes
- [ ] Ant Design components CSS-scoped without Tailwind conflicts
- [ ] 4-layer PII detection pipeline produces confidence scores
- [ ] All 4 MVP connectors (PostgreSQL, MySQL, MongoDB, Snowflake) pass integration tests
- [ ] SSO auth flow works end-to-end (OIDC or SAML)
- [ ] Celery jobs are idempotent with checkpoint resume
- [ ] Circuit breakers engage on LLM/connector failures
- [ ] Quality evaluation produces composite score with heatmap triplets
- [ ] Playwright E2E covers: project → connection → discovery → PII → masking → generation

---

## Vision

Build a comprehensive Test Data Management platform that replaces Delphix for Ameritas. Handles every data type — SQL, NoSQL, cloud DWH, files — using AI to automate schema discovery, PII detection, relationship inference, and synthetic data generation. Professional-grade enterprise UI with visual workflow builder, compliance reporting, and AI assistant.

### Why DataWrangler > Delphix
- Native cloud DWH connectors (Snowflake, Databricks, Redshift) vs. none
- 3 synthetic engines (Faker, Statistical, LLM) vs. reference files only
- Graph-aware subsetting vs. table-level only
- Modern hybrid UI (shadcn + Ant Design) with dark mode vs. outdated, steep-learning-curve UI
- LLM-powered NLP interface vs. no NLP
- GDPR/HIPAA/CCPA compliance reports vs. limited reporting
- Docker-based, self-hosted vs. high cost, complex implementation

---

## Architecture

### Principles
1. **Domain-Driven Design (DDD)** — 7 bounded contexts (connection, discovery, masking, synthetic, subsetting, workflow, compliance), each with entities, value objects, repositories (ABCs), services, and domain events. Domain layer has zero framework dependencies.
2. **Loose Coupling** — DI container (`dependency-injector`), domain events for cross-context communication, interface segregation via ABCs, configuration injection.
3. **Fault Tolerance** — Celery exponential backoff retries, dead letter queue, circuit breakers (`pybreaker`), idempotent jobs with checkpoint resume, graceful degradation (LLM down → Layers 1-3 still work), configurable timeouts, transaction boundaries.

### Backend Structure (DDD Layers)
```
backend/app/
├── domain/           # Pure business logic — ZERO framework deps
│   ├── shared/       # Base Entity, AggregateRoot, ValueObject, DomainEvent, Repository ABC
│   ├── connection/   # Connection, ConnectionCredentials, ConnectorType
│   ├── discovery/    # Schema, Table, Column, Relationship, PIIType, PIIConfidence
│   ├── masking/      # MaskingPolicy, MaskingRule, MaskingStrategy
│   ├── synthetic/    # SyntheticConfig, GenerationPlan, BaseSyntheticEngine
│   ├── subsetting/   # SubsetConfig, DependencyGraph
│   ├── workflow/     # Workflow, WorkflowNode, WorkflowEdge, WorkflowExecutor
│   └── compliance/   # ComplianceReport, AuditEntry, HIPAAReporter, GDPRReporter, CCPAReporter
│
├── application/      # Use cases — Commands, Queries, Handlers, Mediator (CQRS-lite)
├── infrastructure/   # Framework implementations
│   ├── persistence/  # SQLAlchemy repos + ORM models
│   ├── connectors/   # BaseConnector ABC + SQL/NoSQL/Cloud/File implementations
│   ├── ai/           # LLMProvider ABC + Claude/Ollama providers + cost tracking
│   ├── storage/      # StorageBackend ABC + Local/S3/DB implementations
│   ├── auth/         # OIDC, SAML, JWT providers
│   ├── messaging/    # Event bus + Celery app + task handlers
│   └── monitoring/   # Health checks + Prometheus metrics
│
└── api/v1/           # Thin HTTP → command/query mapping (FastAPI)
```

### Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14+ (App Router) + shadcn/ui + Tailwind CSS + Ant Design v5 (data components, CSS-scoped) + 21st.dev + ReactFlow |
| Backend | Python FastAPI (async) + dependency-injector |
| Synthetic | copulas + ctgan + deepecho + Faker + LLM (built from scratch, SDV-inspired architecture) |
| PII Detection | Presidio + spaCy + regex + LLM (4-layer pipeline) |
| LLM | Claude API + Ollama (pluggable provider abstraction) |
| Task Queue | Celery + Redis |
| Database | PostgreSQL (metadata store) |
| Auth | SAML 2.0 / OIDC (authlib) + JWT fallback |
| Storage | Pluggable: Local FS / S3-compatible / DB BLOBs |
| Testing | pytest + Jest + Playwright |
| Monitoring | Flower + Prometheus + structlog (JSON) |
| Containerization | Docker + Docker Compose |

---

## Core Features (10)

### 1. Universal Data Connectivity
- MVP: PostgreSQL, MySQL, MongoDB, Snowflake
- Phase 3: Oracle, SQL Server, Cassandra, DynamoDB, Databricks, Redshift, CSV, JSON, Parquet, Avro
- Pluggable `BaseConnector` ABC with entry-point registration

### 2. AI-Powered Schema Discovery
- `information_schema` introspection (SQL) / document sampling (NoSQL)
- Column statistics: cardinality, null %, min/max, pattern distribution
- Visual schema explorer with interactive tree (Ant Design Tree, CSS-scoped)

### 3. Intelligent PII Detection (4-Layer Pipeline)
- Layer 1: Regex (SSN, credit card, phone, email, IP)
- Layer 2: Presidio + spaCy NER (PERSON, LOCATION, DATE_TIME)
- Layer 3: Column name heuristics
- Layer 4: LLM classification (only when confidence < 0.4 — cost control)
- Weighted confidence scoring: auto-classify >= 0.65, needs-review 0.4-0.65
- Graceful degradation: LLM down → Layers 1-3 still operate

### 4. Relationship Inference
- Declared FKs, naming convention matching, Jaccard overlap, LLM-assisted
- Interactive relationship graph (ReactFlow)

### 5. Synthetic Data Generation (3 Engines)
- **Faker** (fast): PII-type-aware, constraint handling, FK ordering
- **Statistical** (distribution-preserving): GaussianCopula, CTGAN, HMA-inspired multi-table — built from scratch using copulas/ctgan libraries directly
- **LLM** (intelligent): NLP prompts → generation plans → execution, provider-configurable
- Quality evaluation: composite score (0-100), distribution overlays, correlation heatmap triplets, privacy metrics (DCR/NNDR)

### 6. Data Masking (7 Strategies)
- Hash, redact, faker_replace, shuffle, nullify, format-preserving encryption (FF1/FF3-1)
- Deterministic masking (HMAC-SHA256), chunked parallel processing (Celery)
- Side-by-side original vs. transformed preview with color diff

### 7. Graph-Aware Data Subsetting
- FK dependency graph, upstream/downstream traversal, WHERE filters
- Dry-run analysis (row counts per table), target by % or absolute count

### 8. Visual Workflow Builder
- ReactFlow DAG builder: Discover, Mask, Generate, Subset, Export nodes
- Per-node configuration, real-time execution status, cron scheduling
- Dual-mode: visual ↔ JSON DAG definition

### 9. Compliance & Audit
- HIPAA: PHI inventory, access controls, encryption status, BAA tracking
- GDPR: Data mapping, lawful basis, DPIA, right-to-erasure
- CCPA: Consumer data categories, sale/sharing, opt-out
- RBAC (admin/editor/viewer per project), full audit trail

### 10. CI/CD Integration
- REST API (OpenAPI), CLI tool (`datawrangler`), API keys, webhooks

---

## UI/UX Design

### Design System
- **Hybrid**: shadcn/ui + Tailwind CSS (primary) + Ant Design v5 (Table, Tree — CSS Module scoped) + 21st.dev marketplace components
- **Theme**: Dark / Light / System (three-way toggle, CSS variables)
- **Colors**: Ameritas Blue `#1B65A6` primary, full light + dark token sets
- **Typography**: Inter (UI) + JetBrains Mono (code)
- **Icons**: Lucide React

### Competitor-Informed Features (from analysis of 10 platforms)

| Feature | Inspired By | Description |
|---------|------------|-------------|
| **AI Assistant** | MOSTLY AI, Immuta, Databricks | Conversational sidebar for ALL operations — query PII, create rules, generate data, check status. Context-aware per page. 21st.dev AI Chat components. |
| **Quality Visualization** | Gretel SQS, MOSTLY AI | Composite score gauge, overlaid distribution charts (real vs synthetic), correlation heatmap triplets, privacy metrics (DCR/NNDR/identical matches) |
| **Notification Center** | Collibra, Snowflake | In-app inbox, multi-channel (email/Slack), digest options, actionable notifications |
| **Inline Collaboration** | Snowflake, Collibra | Column-level comments, @mentions, masking rule discussions, workflow annotations |
| **Progressive Disclosure** | Airbyte UX Handbook | Minimize fields, smart defaults, "Advanced" toggle, field-level help, fail-fast validation |
| **Onboarding Wizard** | Tonic.ai, Airbyte | 5-step guided flow (Create Project → Add Connection → Discover → Review PII → Mask), skippable, resumable |
| **Side-by-Side Preview** | Tonic.ai Privacy Hub | Original vs transformed with color diff, column slide-out (Settings/Sample/Comments tabs) |
| **PII Heatmap** | Delphix DCT | Grid of tables, color intensity = PII density, unmasked count, click to drill down |
| **Job Gantt Timeline** | Tonic.ai | Temporal overlap view, dependency arrows, zoomable time scale |
| **Dual-Mode Interfaces** | Airbyte, dbt Cloud | Visual editor ↔ JSON/YAML code, bidirectional sync — for masking rules, workflows, subsetting filters |

### 21st.dev Components
| Component | 21st.dev Source |
|-----------|----------------|
| AI Assistant sidebar | AI Chat (78 variants) |
| Command palette (Cmd+K) | `dhileepkumargm/command-palette` |
| Dashboard layout | "Dashboard with Collapsible Sidebar" |
| Stat cards | Cards + Numbers (animated counters) |
| Forms | Inputs, Selects, Date Pickers |
| Notifications | Notifications, Alerts, Badges |
| Empty states | Empty State component |
| Loading | Spinner/Loaders |
| Modals/drawers | Dialogs, Drawer |

### Key Pages
1. **Dashboard** — Stat cards, recent projects, active jobs (SSE), PII donut
2. **Project List** — Table/card toggle, filters, bulk actions
3. **Connections** — Cards with status dots, slide-in form drawer, progressive disclosure
4. **Schema Discovery** — Split-pane: tree (Ant) + column detail with 3 tabs + PII heatmap
5. **PII Results** — Confidence badges, bulk classify, CSV export
6. **Masking** — Policy cards, rule editor with strategy selector, side-by-side preview
7. **Synthetic Generation** — Engine selector cards, NLP prompt interface, editable plan, quality report
8. **Subsetting** — Interactive dependency graph, dry-run analysis, traversal toggle
9. **Workflow Builder** — ReactFlow canvas, node palette, config panel, run history, Gantt view
10. **Jobs** — List + Gantt toggle, SSE progress, per-table breakdown, log viewer
11. **Compliance** — Report generator per regulation, PDF preview, PII coverage dashboard
12. **Admin** — System health, DLQ, key rotation, user management, audit log

---

## SDV-Inspired Architecture (No Code Dependency)

Built from scratch, inspired by SDV's patterns (studied at `/Desktop/sdv`):

| SDV Pattern | DataWrangler Implementation |
|------------|---------------------------|
| Metadata auto-detection + JSON serialization | Own metadata system in `domain/discovery/` |
| `fit()`/`sample()` synthesizer pattern | `BaseSyntheticEngine` ABC with `train()`/`generate()`/`evaluate()` |
| HMA hierarchical multi-table | FK-aware generation with topological sort |
| CAG constraint framework | Business rules: Range, Inequality, FixedCombinations |
| Quality evaluation (KS test) | scipy.stats-based scoring |
| Plugin discovery | Connector entry-point registration |

**Underlying ML libraries used directly**: `copulas`, `ctgan`, `deepecho`, `scipy.stats`
**Zero SDV code dependency** — full ownership, no license concerns.

---

## Implementation Phases

### Phase 1: MVP (10 weeks — Sprints 1-5)
- Backend DDD foundation + DI container + Alembic migrations
- SSO auth (OIDC/SAML) + JWT fallback
- PostgreSQL + MySQL + MongoDB + Snowflake connectors
- Schema discovery + 4-layer PII detection
- Faker synthetic engine
- LLM provider abstraction (Claude + Ollama)
- Frontend: hybrid design system (shadcn + Ant scoped), AppShell, dark/light/system theme, Cmd+K, AI Assistant scaffold, Notification Center
- Dashboard, connections, schema explorer, PII results, synthetic generation UI
- Job monitoring (SSE), onboarding wizard, PII heatmap
- Storage abstraction (local FS), Docker dev environment
- Test infrastructure (pytest, Jest, Playwright)

### Phase 2: Advanced (8 weeks — Sprints 6-9)
- Statistical synthetic engine (copulas/ctgan, built from scratch)
- LLM synthetic engine (NLP prompt → plan → execution)
- Quality evaluation (composite score, heatmap triplets, privacy metrics)
- Masking engine (7 strategies + FPE)
- Graph-aware subsetting
- ReactFlow workflow builder + executor
- Side-by-side preview, dual-mode interfaces, Gantt job view
- Inline collaboration (comments, @mentions)

### Phase 3: Enterprise (8 weeks — Sprints 10-13)
- HIPAA + GDPR + CCPA compliance reports
- RBAC (admin/editor/viewer per project)
- Full audit trail
- CLI tool (`datawrangler` command)
- API keys + webhooks
- Production Docker Compose (Nginx, resource limits, SSL)
- S3 storage backend
- Remaining connectors (Oracle, SQL Server, CSV, JSON, Parquet, Avro)
- Activity feed, compliance collaboration

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| CTGAN training slow on large tables | High | Medium | Row sampling limits (50K default), GaussianCopula as fast alternative |
| SSO integration complexity | Medium | High | Start Sprint 1, JWT fallback if SSO blocks |
| LLM API rate limits / cost | Medium | Medium | Circuit breaker + Ollama fallback + Layer 4 only when conf < 0.4 |
| ReactFlow workflow builder complexity | Medium | High | Timebox 2 sprints, fall back to config-based if needed |
| shadcn + Ant Design CSS conflicts | Medium | Medium | CSS Module scoping, dedicated wrapper components, theme token sync |
| Compliance report requirements unclear | Medium | Medium | Legal/compliance team review before Sprint 10 |

---

## Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Full Spec | `DATAWRANGLER.md` | Complete technical specification with DDD structure, DB schema, API endpoints, AI pipeline, UI wireframes |
| Sprint Plan | `PLANNING.md` (root) | Sprint-level tasks per role (Backend Lead, Data Engineer, Frontend Lead, Platform/DevOps) |
| This File | `projects/datawrangler/PLANNING.md` | SEED ideation output — consolidated decisions and architecture |

---

**Graduated:** 2026-03-28
**Location:** `apps/datawrangler/`
**README:** `apps/datawrangler/README.md`
