# DataWrangler

> AI-Powered Test Data Management Platform — Ameritas' Delphix replacement

---

## Metadata

| Field | Value |
|-------|-------|
| **Type** | Application |
| **Target** | Internal Ameritas tool (single-tenant) |
| **Team** | 4+ developers |
| **Timeline** | 26 weeks (13 sprints, 3 phases) |
| **Deployment** | Docker Compose on VMs |

### Skill Loadout
| Tool | Purpose |
|------|---------|
| PAUL | Managed build orchestration |
| AEGIS | Security audit (OWASP, credential handling, PII) |

### Quality Gates
- [ ] All 7 bounded contexts have entities, value objects, repository ABCs, domain events
- [ ] Hybrid UI renders correctly in light + dark + system modes
- [ ] Ant Design components CSS-scoped without Tailwind conflicts
- [ ] 4-layer PII detection pipeline produces confidence scores
- [ ] All 4 MVP connectors pass integration tests
- [ ] SSO auth flow works end-to-end
- [ ] Celery jobs are idempotent with checkpoint resume
- [ ] Circuit breakers engage on external service failures
- [ ] Quality evaluation produces composite score with heatmap triplets
- [ ] Playwright E2E covers full workflow: project through generation

---

## Overview

DataWrangler is a comprehensive TDM platform that handles SQL, NoSQL, cloud data warehouses, and files. It uses AI to automate schema discovery, PII detection, relationship inference, and synthetic data generation. It replaces Delphix with native cloud connectors, 3 synthetic engines, graph-aware subsetting, a modern hybrid UI with dark mode, LLM-powered NLP, and GDPR/HIPAA/CCPA compliance reporting.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14+ + shadcn/ui + Tailwind CSS + Ant Design v5 (data components, CSS-scoped) + 21st.dev + ReactFlow |
| Backend | Python FastAPI (async) + dependency-injector |
| Synthetic | copulas + ctgan + deepecho + Faker + LLM (SDV-inspired, built from scratch) |
| PII Detection | Presidio + spaCy + regex + LLM (4-layer pipeline) |
| LLM | Claude API + Ollama (pluggable provider abstraction) |
| Task Queue | Celery + Redis |
| Database | PostgreSQL (metadata store) |
| Auth | SAML 2.0 / OIDC (authlib) + JWT fallback |
| Storage | Pluggable: Local FS / S3-compatible / DB BLOBs |
| Testing | pytest + Jest + Playwright |
| Monitoring | Flower + Prometheus + structlog (JSON) |

---

## Architecture

### Principles
1. **Domain-Driven Design** — 7 bounded contexts (connection, discovery, masking, synthetic, subsetting, workflow, compliance). Domain layer has zero framework dependencies.
2. **Loose Coupling** — DI container, domain events for cross-context communication, interface segregation via ABCs, configuration injection.
3. **Fault Tolerance** — Exponential backoff retries, dead letter queue, circuit breakers (`pybreaker`), idempotent jobs with checkpoint resume, graceful degradation, configurable timeouts.

### Backend Structure
```
backend/app/
├── domain/           # Pure business logic (ZERO framework deps)
│   ├── shared/       # Entity, AggregateRoot, ValueObject, DomainEvent, Repository ABC
│   ├── connection/   # Connection, ConnectionCredentials, ConnectorType
│   ├── discovery/    # Schema, Table, Column, Relationship, PIIType, PIIConfidence
│   ├── masking/      # MaskingPolicy, MaskingRule, MaskingStrategy
│   ├── synthetic/    # SyntheticConfig, GenerationPlan, BaseSyntheticEngine
│   ├── subsetting/   # SubsetConfig, DependencyGraph
│   ├── workflow/     # Workflow, WorkflowNode, WorkflowEdge, WorkflowExecutor
│   └── compliance/   # ComplianceReport, HIPAAReporter, GDPRReporter, CCPAReporter
├── application/      # Commands, Queries, Handlers, Mediator (CQRS-lite)
├── infrastructure/   # SQLAlchemy repos, connectors, AI providers, storage, auth, messaging, monitoring
└── api/v1/           # Thin FastAPI routes → command/query mapping
```

### Data Model (PostgreSQL)
Core tables: users, projects, connections, discovered_schemas, discovered_tables, discovered_columns, discovered_relationships, masking_policies, masking_rules, synthetic_configs, subset_configs, workflows, jobs, job_logs, dead_letter_jobs, audit_logs, compliance_reports.

### API Surface
REST API at `/api/v1/` with endpoints for: auth (SSO + JWT), projects CRUD, connections (CRUD + test + schemas), discovery (run + results + PII + relationships), masking (policies + rules + preview + execute), synthetic (configs + preview + generate + NLP + quality), subsetting (configs + analyze + execute), jobs (list + detail + cancel + retry + SSE stream), workflows (CRUD + execute), compliance (generate + list + download), admin (health + DLQ + key rotation).

---

## Design Decisions

1. **Hybrid UI** — shadcn/ui + Tailwind CSS as primary, Ant Design v5 only for Table and Tree (CSS Module scoped). 21st.dev components for AI chat, command palette, dashboard layouts.
2. **Dark/Light/System theme** — Three-way toggle via CSS variables. Ant Design tokens synced.
3. **SDV-inspired, not SDV-dependent** — Build synthetic engines from scratch using copulas/ctgan/deepecho directly. Zero SDV code dependency, no license concerns.
4. **LLM provider abstraction** — Claude API + Ollama behind `LLMProvider` ABC. PII Layer 4 only triggers when confidence < 0.4 (cost control). Self-hosted option for cost-sensitive deployments.
5. **SSO-first auth** — SAML/OIDC integration for Ameritas corporate identity. JWT fallback for service accounts and CI/CD.
6. **Pluggable storage** — `StorageBackend` ABC with local FS (default), S3-compatible, and DB BLOB implementations. Selected via env var.
7. **Progressive disclosure UX** — All config forms follow Airbyte pattern: minimal fields, smart defaults, collapsible advanced section, field-level help.
8. **AI Assistant on every page** — Conversational sidebar (21st.dev AI Chat) for querying PII status, creating rules, generating data, checking jobs. Context-aware per page.
9. **Quality visualization** — Composite score (0-100), overlaid distribution charts, correlation heatmap triplets (original/synthetic/difference), privacy metrics (DCR/NNDR/identical matches). Inspired by Gretel SQS and MOSTLY AI.
10. **Dual-mode interfaces** — Visual editor and JSON/YAML code editor with bidirectional sync for masking rules, workflows, and subsetting filters.

---

## UI/UX

### Design System
| Aspect | Choice |
|--------|--------|
| Primary UI | shadcn/ui + Tailwind CSS + Radix UI |
| Data components | Ant Design v5 Table, Tree (CSS Module scoped) |
| Charts | Recharts |
| Graph visualization | ReactFlow |
| Marketplace | 21st.dev (AI chat, command palette, dashboard, stat cards) |
| Icons | Lucide React |
| Theme | Dark / Light / System (CSS variables) |
| Colors | Ameritas Blue `#1B65A6` primary |
| Typography | Inter (UI) + JetBrains Mono (code) |

### Key Pages (12)
1. Dashboard (stat cards, projects, jobs, PII donut)
2. Project List (table/card toggle, filters)
3. Connections (status cards, progressive disclosure form)
4. Schema Discovery (tree + column detail + PII heatmap)
5. PII Results (confidence badges, bulk actions)
6. Masking (policy cards, rule editor, side-by-side preview)
7. Synthetic Generation (engine selector, NLP prompt, quality report)
8. Subsetting (dependency graph, dry-run analysis)
9. Workflow Builder (ReactFlow canvas, Gantt view)
10. Jobs (list + Gantt toggle, SSE progress, log viewer)
11. Compliance (report generator, PDF preview)
12. Admin (health, DLQ, users, audit log)

### Competitor-Informed Features
- AI Assistant sidebar (MOSTLY AI, Immuta, Databricks Genie)
- Quality heatmap triplets + privacy metrics (Gretel, MOSTLY AI)
- Notification Center with multi-channel (Collibra, Snowflake)
- Inline collaboration with @mentions (Snowflake, Collibra)
- Progressive disclosure config (Airbyte UX Handbook)
- Guided onboarding wizard (Tonic.ai, Airbyte)
- Side-by-side data preview with color diff (Tonic.ai)
- PII heatmap (Delphix DCT)
- Job Gantt timeline (Tonic.ai)
- Dual-mode interfaces (Airbyte, dbt Cloud)

---

## Core Features

### 1. Universal Data Connectivity
MVP: PostgreSQL, MySQL, MongoDB, Snowflake. Phase 3: Oracle, SQL Server, Cassandra, DynamoDB, Databricks, Redshift, CSV, JSON, Parquet, Avro. Pluggable `BaseConnector` ABC with entry-point registration.

### 2. Schema Discovery
`information_schema` introspection (SQL) / document sampling (NoSQL). Column statistics, visual tree explorer.

### 3. PII Detection (4-Layer Pipeline)
Regex → Presidio+spaCy → Column heuristics → LLM (fallback only). Weighted confidence scoring. Graceful degradation if LLM unavailable.

### 4. Relationship Inference
Declared FKs + naming conventions + Jaccard overlap + LLM-assisted. Interactive ReactFlow graph.

### 5. Synthetic Data (3 Engines)
Faker (fast) + Statistical/copulas/ctgan (distribution-preserving) + LLM (NLP-driven). Quality evaluation with composite score, distribution overlays, heatmap triplets, privacy metrics.

### 6. Data Masking (7 Strategies)
Hash, redact, faker_replace, shuffle, nullify, FPE (FF1/FF3-1). Deterministic masking. Chunked parallel processing.

### 7. Graph-Aware Subsetting
FK dependency graph traversal (upstream/downstream). WHERE filters. Dry-run analysis.

### 8. Visual Workflow Builder
ReactFlow DAG builder with 5 node types. Per-node config. Cron scheduling. Dual-mode (visual + JSON).

### 9. Compliance & Audit
HIPAA + GDPR + CCPA report generators. RBAC per project. Full audit trail.

### 10. CI/CD Integration
REST API (OpenAPI), CLI tool, API keys, webhooks.

---

## Implementation Phases

### Phase 1: MVP (10 weeks, Sprints 1-5)
Backend DDD foundation, SSO auth, 4 connectors, schema discovery, PII detection, Faker engine, LLM provider abstraction, hybrid frontend with dark mode, dashboard, connections, schema explorer, PII heatmap, job monitoring, onboarding wizard, AI assistant scaffold, notification center, storage abstraction, Docker dev, test infrastructure.

### Phase 2: Advanced (8 weeks, Sprints 6-9)
Statistical + LLM synthetic engines, quality evaluation, masking engine (7 strategies + FPE), subsetting, workflow builder + executor, side-by-side preview, dual-mode interfaces, Gantt view, collaboration.

### Phase 3: Enterprise (8 weeks, Sprints 10-13)
Compliance reports (HIPAA/GDPR/CCPA), RBAC, audit trail, CLI, API keys, webhooks, production Docker Compose, S3 storage, remaining connectors, activity feed.

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| CTGAN training slow on large tables | Row sampling limits (50K), GaussianCopula alternative |
| SSO integration complexity | Start Sprint 1, JWT fallback |
| LLM cost/rate limits | Circuit breaker, Ollama fallback, Layer 4 only at low confidence |
| Workflow builder complexity | Timebox 2 sprints, config-based fallback |
| shadcn + Ant CSS conflicts | CSS Module scoping, wrapper components, token sync |
| Compliance requirements unclear | Legal team review before Sprint 10 |

---

## Deploy

### Development
```bash
cp .env.example .env
make dev   # docker compose -f docker-compose.dev.yml up
```
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Flower: http://localhost:5555

### Production
Docker Compose on VMs with Nginx reverse proxy, SSL termination, resource limits, external volumes, `unless-stopped` restart policies.

---

## Open Questions

1. Which SSO provider does Ameritas use? (Okta, Azure AD, other?) — affects Sprint 1 implementation.
2. What Snowflake instance/credentials are available for connector testing?
3. Does Ameritas legal have specific templates for HIPAA/GDPR/CCPA reports?
4. What Slack/Teams channels should webhook notifications target?
5. Is there an existing CI/CD pipeline (GitHub Actions, Jenkins, etc.) to integrate with?

---

## References

| Document | Location |
|----------|----------|
| Full Technical Spec | `../../DATAWRANGLER.md` |
| Sprint-Level Plan | `../../PLANNING.md` |
| SEED Ideation | `../../projects/datawrangler/PLANNING.md` |
