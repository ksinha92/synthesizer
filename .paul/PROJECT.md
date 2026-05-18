# DataWrangler

## What This Is

AI-Powered Test Data Management Platform that replaces Delphix for Ameritas. Handles SQL, NoSQL, cloud data warehouses, and files using AI to automate schema discovery, PII detection, relationship inference, and synthetic data generation. Professional-grade enterprise UI with visual workflow builder, compliance reporting, and AI assistant.

## Core Value

QA and dev teams can discover, mask, generate, and subset test data across any data source — with AI-powered PII detection, 3 synthetic engines, and full GDPR/HIPAA/CCPA compliance — in a single, modern platform that replaces Delphix.

## Current State

| Attribute | Value |
|-----------|-------|
| Type | Application |
| Version | 0.0.0 |
| Status | Initializing |
| Last Updated | 2026-03-28 |

## Requirements

### Core Features

1. **Universal Data Connectivity** — MVP: PostgreSQL, MySQL, MongoDB, Snowflake. Pluggable `BaseConnector` ABC with entry-point registration.
2. **AI-Powered Schema Discovery** — `information_schema` introspection (SQL) / document sampling (NoSQL). Column statistics, visual tree explorer.
3. **Intelligent PII Detection** — 4-layer pipeline: Regex → Presidio+spaCy → Column heuristics → LLM (fallback only, confidence < 0.4). Weighted scoring with auto-classify/needs-review thresholds.
4. **Relationship Inference** — Declared FKs + naming conventions + Jaccard overlap + LLM-assisted. Interactive ReactFlow graph.
5. **Synthetic Data Generation (3 Engines)** — Faker (fast), Statistical/copulas/ctgan (distribution-preserving, SDV-inspired architecture built from scratch), LLM (NLP-driven). Quality evaluation with composite score.
6. **Data Masking (7 Strategies)** — Hash, redact, faker_replace, shuffle, nullify, FPE (FF1/FF3-1). Deterministic masking. Chunked parallel processing.
7. **Graph-Aware Data Subsetting** — FK dependency graph traversal (upstream/downstream). WHERE filters. Dry-run analysis.
8. **Visual Workflow Builder** — ReactFlow DAG builder with 5 node types. Per-node config. Cron scheduling. Dual-mode (visual + JSON).
9. **Compliance & Audit** — HIPAA + GDPR + CCPA report generators. RBAC per project. Full audit trail.
10. **CI/CD Integration** — REST API (OpenAPI), CLI tool (`datawrangler`), API keys, webhooks.

### Validated (Shipped)
None yet.

### Active (In Progress)
None yet.

### Planned (Next)
- Phase 1 (MVP): Backend DDD foundation, SSO auth, 4 connectors, discovery, PII detection, Faker engine, LLM provider abstraction, hybrid frontend, dashboard, job monitoring
- Phase 2 (Advanced): Statistical + LLM synthetic engines, quality evaluation, masking engine, subsetting, workflow builder
- Phase 3 (Enterprise): Compliance reports, RBAC, audit trail, CLI, production deployment

### Out of Scope
- Multi-tenancy (internal Ameritas tool, single-tenant)
- Kubernetes deployment (Docker Compose on VMs)
- Using SDV as a dependency (architecture inspiration only, built from scratch)
- Mobile app (responsive web only)

## Constraints

### Technical Constraints
- Domain layer must have ZERO framework dependencies (DDD principle)
- Ant Design v5 components (Table, Tree only) must be CSS Module scoped to prevent Tailwind conflicts
- LLM PII detection (Layer 4) only triggers when confidence < 0.4 to control costs
- Celery jobs must be idempotent with checkpoint resume for fault tolerance
- SDV BUSL-1.1 license — no code dependency, architecture inspiration only

### Business Constraints
- Internal Ameritas tool — SSO via corporate identity provider (SAML/OIDC)
- All three compliance frameworks equally important (HIPAA, GDPR, CCPA)
- 4+ developer team, 26-week timeline
- Legal/compliance team review required before Sprint 10 (compliance reports)

## Key Decisions

| Decision | Rationale | Date | Status |
|----------|-----------|------|--------|
| DDD with 7 bounded contexts | Clean domain separation, zero framework deps in domain layer | 2026-03-28 | Resolved |
| Hybrid UI: shadcn/Tailwind + Ant Design (scoped) + 21st.dev | Modern SaaS look (shadcn) + enterprise data components (Ant Table/Tree) + marketplace components (21st.dev AI chat, command palette) | 2026-03-28 | Resolved |
| Dark/Light/System theme | Competitive parity with Snowflake/MOSTLY AI; CSS variables with three-way toggle | 2026-03-28 | Resolved |
| SDV-inspired, not SDV-dependent | Build from scratch using copulas/ctgan/deepecho directly; avoids BUSL-1.1 license, full code ownership | 2026-03-28 | Resolved |
| Claude API + Ollama (pluggable LLM) | Provider abstraction; Claude for quality, Ollama for cost-sensitive deployments | 2026-03-28 | Resolved |
| SSO-first auth (SAML/OIDC) | Ameritas corporate identity integration; JWT fallback for service accounts | 2026-03-28 | Resolved |
| Pluggable storage backend | Local FS (default) + S3-compatible + DB BLOBs; selected via env var | 2026-03-28 | Resolved |
| Docker Compose on VMs (not K8s) | Simpler ops for internal tool; Nginx reverse proxy for SSL | 2026-03-28 | Resolved |
| Progressive disclosure UX (Airbyte pattern) | Minimize fields, smart defaults, field-level help; competitor analysis validated | 2026-03-28 | Resolved |
| AI Assistant on every page | Conversational sidebar using 21st.dev AI Chat; context-aware per page; covers all operations | 2026-03-28 | Resolved |

## Success Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| MVP connectors passing integration tests | 4 (PG, MySQL, Mongo, Snowflake) | 0 | Not started |
| PII detection pipeline accuracy | >= 0.65 auto-classify threshold | - | Not started |
| Synthetic quality composite score | >= 85/100 | - | Not started |
| SSO auth end-to-end working | OIDC or SAML flow | - | Not started |
| Playwright E2E coverage | Full workflow (project→generation) | 0 | Not started |
| Dark/Light/System theme rendering | All pages, no visual bugs | - | Not started |
| Compliance reports generated | HIPAA + GDPR + CCPA | 0/3 | Not started |

## Tech Stack / Tools

| Layer | Technology | Notes |
|-------|------------|-------|
| Frontend | Next.js 14+ (App Router) + shadcn/ui + Tailwind CSS | Primary UI framework |
| Data Components | Ant Design v5 (Table, Tree) | CSS Module scoped, isolated |
| UI Marketplace | 21st.dev | AI chat, command palette, dashboards, stat cards |
| Graph Viz | ReactFlow | Workflow builder, relationship graph, subsetting graph |
| Charts | Recharts | Distribution comparisons, quality scores, heatmaps |
| Icons | Lucide React | Consistent icon set |
| Backend | Python FastAPI (async) | Auto-generated API docs |
| DI Container | dependency-injector | Wires infrastructure → domain |
| Synthetic | copulas + ctgan + deepecho + Faker | Built from scratch, SDV-inspired |
| PII Detection | Presidio + spaCy + regex | 4-layer pipeline |
| LLM | Claude API + Ollama | Pluggable provider abstraction |
| Task Queue | Celery + Redis | Async jobs with retry policies |
| Database | PostgreSQL | Metadata store |
| Auth | authlib (OIDC/SAML) + JWT | SSO + service accounts |
| Storage | Local FS / S3 / DB BLOBs | Pluggable via env var |
| Monitoring | Flower + Prometheus + structlog | Task visibility + metrics + JSON logging |
| Testing | pytest + Jest + Playwright | Unit + integration + E2E |
| Circuit Breaker | pybreaker | Fault tolerance for external calls |
| Containerization | Docker + Docker Compose | Dev and production |

## Specialized Flows

See: .paul/SPECIAL-FLOWS.md

Quick Reference:
- /aegis:audit → Security review (required, not yet installed)

---
*Created: 2026-03-28*
