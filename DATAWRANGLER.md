# DataWrangler: AI-Powered Test Data Management Platform

> A next-generation TDM platform that surpasses Delphix with AI-driven synthetic data generation, universal data source support, and a professional enterprise UI.

---

## Vision

Build a comprehensive Test Data Management solution that handles every data type — SQL, NoSQL, structured, semi-structured, and unstructured — using NLP and AI to automate schema discovery, PII detection, relationship inference, and realistic synthetic data generation. Everything an organization needs to run a successful TDM program.

**Target**: Internal Ameritas tool (single-tenant), deployed on Ameritas infrastructure for internal QA/dev teams.

---

## Why DataWrangler > Delphix

| Delphix Limitation | DataWrangler Solution |
|---|---|
| No native cloud DWH support (Snowflake, Databricks) | Native connectors for Snowflake, Databricks, Redshift |
| Limited synthetic data (reference files only) | 3 engines: Faker (fast), Statistical (distribution-preserving), LLM (intelligent) |
| Table-level subsetting only | Graph-aware subsetting with upstream/downstream traversal |
| Outdated, difficult UI with steep learning curve | Modern Next.js + Ant Design with visual schema explorer + drag-and-drop workflows |
| Slow masking performance | Chunked parallel processing via Celery workers; horizontal scaling |
| No NLP interface | LLM-powered natural language data generation and schema understanding |
| Limited reporting | Built-in GDPR/HIPAA/CCPA compliance reports with full audit trails |
| High cost, complex implementation | Open-source core, Docker-based, self-hosted |

---

## Architectural Principles

### Domain-Driven Design (DDD)
The backend is structured around **bounded contexts** rather than technical layers. Each domain module (connection, discovery, masking, synthetic, subsetting, workflow, compliance) owns its entities, value objects, repositories (ABCs), domain services, and domain events. The domain layer has **zero framework dependencies** — no SQLAlchemy, no FastAPI, no Celery.

### Loose Coupling
- **Dependency Injection**: DI container (e.g., `dependency-injector`) wires infrastructure implementations to domain ABCs
- **Event-Driven Communication**: Bounded contexts communicate via domain events, not direct calls
  - Discovery publishes `PIIDetected` → Masking subscribes to auto-suggest rules
  - Workflow publishes `WorkflowStepCompleted` → Job tracking updates
- **Interface Segregation**: Each connector, engine, and storage backend implements a narrow ABC
- **Configuration Injection**: All infrastructure details (DB URLs, LLM keys, storage paths) are injected, never hard-coded

### Fault Tolerance
- **Celery retry policies**: Exponential backoff with max retries per task type
  - Discovery tasks: 3 retries, 30s/60s/120s backoff
  - Masking tasks: 2 retries (idempotent via chunk tracking)
  - LLM tasks: 5 retries with jitter (API rate limits)
- **Dead letter queue**: Failed tasks after max retries → DLQ for manual review
- **Circuit breaker**: For external services (LLM APIs, data source connections) via `pybreaker` — open after 5 failures, half-open after 60s
- **Idempotent operations**: Jobs have unique IDs; re-running a job resumes from last checkpoint
- **Graceful degradation**: LLM down → PII detection falls back to Layers 1-3, flagged for review; Redis down → API works in sync mode
- **Timeout management**: All external calls have configurable timeouts
- **Transaction boundaries**: Each command handler runs in a single DB transaction; domain events dispatch after commit

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend** | Next.js 14+ (App Router) + React + shadcn/ui + Tailwind CSS + Ant Design v5 (data components) + 21st.dev | Hybrid: modern SaaS UI (shadcn) + enterprise data tables (Ant), 21st.dev marketplace components |
| **Backend** | Python FastAPI (async) | AI/ML ecosystem, async I/O, auto-generated API docs |
| **Synthetic Data** | copulas + ctgan + deepecho + Faker + LLM | Statistical relationship preservation + fast generation + intelligent NLP |
| **NLP/PII Detection** | Microsoft Presidio + spaCy + LLM API | Multi-layer detection: regex, NER, heuristics, LLM |
| **LLM Providers** | Claude API (Anthropic SDK) + Ollama (self-hosted) | Pluggable LLM backend; Claude for quality, Ollama for cost control |
| **Database Connectors** | SQLAlchemy, PyMongo, snowflake-connector-python, Pandas | Universal data source coverage |
| **Task Queue** | Celery + Redis | Low-latency async job processing, horizontal scaling |
| **Metadata Store** | PostgreSQL | Relational metadata, audit trails, compliance |
| **Auth** | SAML 2.0 / OIDC (authlib or python-saml3) | SSO integration with Ameritas corporate identity (Okta/Azure AD) |
| **File Storage** | Pluggable: Local FS / S3-compatible / DB BLOBs | Configurable via `STORAGE_BACKEND` env var |
| **Containerization** | Docker + Docker Compose | Reproducible development and deployment |
| **State Management** | Zustand | Lightweight, fast frontend state |
| **Monitoring** | Flower (Celery) + Prometheus metrics | Task visibility, request/job metrics |
| **Logging** | structlog (JSON) | Structured logging to stdout for infrastructure collection |
| **DI Container** | dependency-injector | Wires infrastructure → domain layer |
| **Circuit Breaker** | pybreaker | Fault tolerance for external service calls |
| **Testing** | pytest + Jest + Playwright | Unit, integration, and E2E test coverage |

---

## Core Features

### 1. Universal Data Connectivity
- **SQL Databases**: PostgreSQL, MySQL (MVP); Oracle, SQL Server (Phase 3)
- **NoSQL Databases**: MongoDB (MVP); Cassandra, DynamoDB (Phase 3)
- **Cloud Data Warehouses**: Snowflake (MVP); Databricks, Redshift (Phase 3)
- **File Formats**: CSV, JSON, Parquet, Avro (Phase 3)
- Pluggable connector architecture — each connector implements `BaseConnector` ABC via entry-point registration

### 2. AI-Powered Schema Discovery
- Automatic schema introspection via `information_schema` (SQL) or document sampling (NoSQL)
- Column statistics: cardinality, null percentage, min/max, pattern distribution
- Visual schema explorer with interactive tree navigation

### 3. Intelligent PII Detection (4-Layer Pipeline)
- **Layer 1 — Regex**: High-precision pattern matching (SSN, credit card, phone, email, IP)
- **Layer 2 — Presidio + spaCy NER**: Entity recognition (PERSON, LOCATION, DATE_TIME, etc.)
- **Layer 3 — Column Name Heuristics**: Match against known PII naming patterns
- **Layer 4 — LLM Classification**: LLM API for ambiguous cases (only when confidence < 0.4 from Layers 1-3)
- Weighted confidence scoring with auto-classify (>=0.65) and needs-review (0.4-0.65) thresholds
- **Graceful degradation**: If LLM provider is down, Layers 1-3 still operate; ambiguous columns flagged for manual review

### 4. Relationship Inference
- Import declared foreign keys from database metadata
- Naming convention matching (`table_b.table_a_id` -> `table_a.id`)
- Value overlap analysis (Jaccard similarity)
- LLM-assisted inference for complex schemas
- Interactive relationship graph visualization

### 5. Synthetic Data Generation (3 Engines)
- **Faker Engine** (Fast): PII-type-aware provider mapping, constraint handling, FK ordering
- **Statistical Engine** (Distribution-Preserving): GaussianCopula for distributions, CTGAN for complex patterns, HMA-inspired approach for multi-table relationships. Built from scratch using `copulas`, `ctgan`, and `deepecho` libraries directly — inspired by SDV's architecture but fully owned.
- **LLM Engine** (Intelligent): Natural language prompts → structured generation plans → execution
  - Example: *"Generate 1000 insurance claims where 20% are auto claims with amounts $500-$50K"*
  - Provider-configurable: Claude API or self-hosted Ollama
  - Basic cost tracking (token counts per job)
- **Quality Evaluation**: Statistical quality scoring (0-100) comparing synthetic vs. real data using KS tests, column shape, and column pair metrics

### 6. Data Masking
- Strategy pattern: hash, redact, faker_replace, shuffle, nullify, format-preserving encryption (FF1/FF3-1)
- Deterministic masking via HMAC-SHA256 with project-scoped salt
- Chunked parallel processing (10K row batches via Celery)
- Side-by-side before/after preview
- Referential integrity maintained across chunks via deterministic mapping

### 7. Graph-Aware Data Subsetting
- Build FK dependency graph from discovered relationships
- Traverse upstream (child->parent) or downstream (parent->child) from root tables
- User-defined WHERE filters on root tables
- Dry-run analysis showing row counts per table before execution
- Target by percentage or absolute row count

### 8. Visual Workflow Builder
- Drag-and-drop DAG builder using ReactFlow
- Node types: Discover, Mask, Generate, Subset, Export
- Connect nodes to define execution order
- Per-node configuration panel
- Real-time execution status per node
- Schedulable via cron expressions

### 9. Compliance & Audit
- **HIPAA**: PHI inventory, access controls, encryption status, BAA tracking
- **GDPR**: Data mapping, lawful basis, DPIA, right-to-erasure support
- **CCPA**: Consumer data categories, sale/sharing tracking, opt-out support
- Each regulation has its own report template and data model
- Full audit trail: every API call logged with user, action, resource, timestamp
- PII coverage dashboard: what's detected, what's masked, what's pending
- Role-based access control (admin/editor/viewer per project)

### 10. CI/CD Integration
- REST API with OpenAPI/Swagger documentation
- CLI tool (`datawrangler` command) for pipeline integration
- API key authentication for automated workflows
- Webhook notifications on job completion/failure

---

## Project Structure (DDD)

```
ameritas-datawrangler/
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── .env.example
├── Makefile
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── playwright.config.ts
│   ├── src/
│   │   ├── app/                        # Next.js App Router
│   │   │   ├── layout.tsx              # Root layout with ThemeProvider (shadcn + Ant scoped)
│   │   │   ├── page.tsx                # Dashboard
│   │   │   ├── (auth)/login/
│   │   │   ├── projects/
│   │   │   │   ├── page.tsx            # Project list
│   │   │   │   └── [projectId]/
│   │   │   │       ├── connections/
│   │   │   │       ├── discovery/
│   │   │   │       ├── masking/
│   │   │   │       ├── synthetic/
│   │   │   │       ├── subsetting/
│   │   │   │       ├── workflows/
│   │   │   │       └── jobs/
│   │   │   └── admin/
│   │   ├── components/
│   │   │   ├── layout/ (AppShell, Sidebar, Header)
│   │   │   ├── connections/ (ConnectionForm, ConnectionList, TestButton)
│   │   │   ├── schema/ (SchemaExplorer, RelationshipGraph, ColumnDrawer)
│   │   │   ├── discovery/ (PIIResultsTable, ClassificationBadge)
│   │   │   ├── synthetic/ (GenerationConfigForm, PreviewTable, NLPPromptInput)
│   │   │   ├── masking/ (RuleEditor, PolicyList, MaskingPreview)
│   │   │   ├── workflows/ (WorkflowCanvas, NodePalette, RunHistory)
│   │   │   ├── jobs/ (JobMonitor, JobList, LogViewer)
│   │   │   └── common/ (DataTable, StatusBadge, ConfirmModal)
│   │   ├── hooks/ (useApi, useSSE, useProject)
│   │   ├── stores/ (projectStore, jobStore)
│   │   └── theme/ (themeConfig)
│   └── tests/
│       ├── unit/                       # Jest + React Testing Library
│       └── e2e/                        # Playwright E2E tests
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py                     # FastAPI app factory + DI container setup
│   │   ├── config.py                   # Pydantic Settings
│   │   ├── container.py                # dependency-injector container
│   │   │
│   │   ├── domain/                     # Domain layer (ZERO framework dependencies)
│   │   │   ├── shared/
│   │   │   │   ├── entity.py           # Base Entity, AggregateRoot
│   │   │   │   ├── value_object.py     # Base ValueObject
│   │   │   │   ├── event.py            # Base DomainEvent
│   │   │   │   └── repository.py       # Base Repository ABC
│   │   │   ├── connection/
│   │   │   │   ├── entities.py         # Connection, ConnectionCredentials
│   │   │   │   ├── value_objects.py    # ConnectorType, ConnectionStatus
│   │   │   │   ├── repository.py       # ConnectionRepository ABC
│   │   │   │   ├── services.py         # ConnectionTestService
│   │   │   │   └── events.py           # ConnectionTested, ConnectionFailed
│   │   │   ├── discovery/
│   │   │   │   ├── entities.py         # Schema, Table, Column, Relationship
│   │   │   │   ├── value_objects.py    # PIIType, PIIConfidence, Classification
│   │   │   │   ├── repository.py       # DiscoveryRepository ABC
│   │   │   │   ├── services.py         # SchemaDiscoveryService, PIIDetectionService
│   │   │   │   └── events.py           # DiscoveryCompleted, PIIDetected
│   │   │   ├── masking/
│   │   │   │   ├── entities.py         # MaskingPolicy, MaskingRule
│   │   │   │   ├── value_objects.py    # MaskingStrategy, MaskingConfig
│   │   │   │   ├── repository.py
│   │   │   │   ├── services.py         # MaskingEngine
│   │   │   │   └── events.py           # MaskingJobCompleted
│   │   │   ├── synthetic/
│   │   │   │   ├── entities.py         # SyntheticConfig, GenerationPlan
│   │   │   │   ├── value_objects.py    # GenerationMethod, EngineType
│   │   │   │   ├── repository.py
│   │   │   │   ├── services.py         # BaseSyntheticEngine, FakerEngine, StatisticalEngine, LLMEngine
│   │   │   │   └── events.py           # GenerationCompleted
│   │   │   ├── subsetting/
│   │   │   │   ├── entities.py         # SubsetConfig, DependencyGraph
│   │   │   │   ├── services.py         # SubsettingEngine
│   │   │   │   └── events.py
│   │   │   ├── workflow/
│   │   │   │   ├── entities.py         # Workflow, WorkflowNode, WorkflowEdge
│   │   │   │   ├── services.py         # WorkflowExecutor
│   │   │   │   └── events.py           # WorkflowStepCompleted, WorkflowFailed
│   │   │   └── compliance/
│   │   │       ├── entities.py         # ComplianceReport, AuditEntry
│   │   │       ├── services.py         # HIPAAReporter, GDPRReporter, CCPAReporter
│   │   │       └── events.py
│   │   │
│   │   ├── application/                # Application layer (use cases / orchestration)
│   │   │   ├── shared/
│   │   │   │   ├── command.py          # Base Command
│   │   │   │   ├── query.py            # Base Query
│   │   │   │   └── mediator.py         # Command/Query mediator
│   │   │   ├── connection/
│   │   │   │   ├── commands.py         # CreateConnection, TestConnection, DeleteConnection
│   │   │   │   ├── queries.py          # GetConnection, ListConnections
│   │   │   │   └── handlers.py
│   │   │   ├── discovery/
│   │   │   │   ├── commands.py         # RunDiscovery, OverridePIIClassification
│   │   │   │   ├── queries.py          # GetDiscoveryResults, GetPIIClassifications
│   │   │   │   └── handlers.py
│   │   │   ├── masking/
│   │   │   │   ├── commands.py
│   │   │   │   ├── queries.py
│   │   │   │   └── handlers.py
│   │   │   ├── synthetic/
│   │   │   │   ├── commands.py
│   │   │   │   ├── queries.py
│   │   │   │   └── handlers.py
│   │   │   ├── subsetting/
│   │   │   │   ├── commands.py
│   │   │   │   ├── queries.py
│   │   │   │   └── handlers.py
│   │   │   ├── workflow/
│   │   │   │   ├── commands.py
│   │   │   │   ├── queries.py
│   │   │   │   └── handlers.py
│   │   │   └── compliance/
│   │   │       ├── commands.py
│   │   │       ├── queries.py
│   │   │       └── handlers.py
│   │   │
│   │   ├── infrastructure/             # Infrastructure layer (framework implementations)
│   │   │   ├── persistence/
│   │   │   │   ├── sqlalchemy/         # SQLAlchemy repository implementations
│   │   │   │   │   ├── connection_repo.py
│   │   │   │   │   ├── discovery_repo.py
│   │   │   │   │   ├── masking_repo.py
│   │   │   │   │   ├── synthetic_repo.py
│   │   │   │   │   ├── workflow_repo.py
│   │   │   │   │   └── compliance_repo.py
│   │   │   │   ├── models/             # ORM models (map to/from domain entities)
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── user.py, project.py, connection.py
│   │   │   │   │   ├── schema_metadata.py, discovery.py
│   │   │   │   │   ├── masking.py, synthetic.py
│   │   │   │   │   ├── workflow.py, job.py, audit.py
│   │   │   │   └── database.py         # Async SQLAlchemy engine + session
│   │   │   ├── connectors/             # Data source abstraction
│   │   │   │   ├── base.py             # BaseConnector ABC
│   │   │   │   ├── registry.py         # Connector factory (entry-point based)
│   │   │   │   ├── sql/
│   │   │   │   │   ├── postgresql.py
│   │   │   │   │   ├── mysql.py
│   │   │   │   │   ├── oracle.py       # Phase 3
│   │   │   │   │   └── sqlserver.py    # Phase 3
│   │   │   │   ├── nosql/
│   │   │   │   │   ├── mongodb.py
│   │   │   │   │   ├── cassandra.py    # Phase 3
│   │   │   │   │   └── dynamodb.py     # Phase 3
│   │   │   │   ├── cloud/
│   │   │   │   │   ├── snowflake.py
│   │   │   │   │   ├── databricks.py   # Phase 3
│   │   │   │   │   └── redshift.py     # Phase 3
│   │   │   │   └── file/               # Phase 3
│   │   │   │       ├── csv.py, json.py, parquet.py, avro.py
│   │   │   ├── ai/                     # LLM provider abstraction
│   │   │   │   ├── llm_provider.py     # LLMProvider ABC: complete, classify, generate_structured
│   │   │   │   ├── claude_provider.py  # Claude API (Anthropic SDK)
│   │   │   │   ├── ollama_provider.py  # Self-hosted via Ollama
│   │   │   │   └── config.py           # Provider selection, fallback chain, cost tracking
│   │   │   ├── storage/                # File storage backends
│   │   │   │   ├── base.py             # StorageBackend ABC: save, load, delete, list, get_url
│   │   │   │   ├── local.py            # LocalFilesystemStorage (volume mount)
│   │   │   │   ├── s3.py              # S3Storage (boto3, works with MinIO locally)
│   │   │   │   └── database.py         # DatabaseBlobStorage (PostgreSQL large objects)
│   │   │   ├── auth/                   # SSO integration
│   │   │   │   ├── oidc.py             # OIDC provider (Okta, Azure AD)
│   │   │   │   ├── saml.py             # SAML 2.0 provider
│   │   │   │   └── jwt.py              # JWT for service accounts / API keys
│   │   │   ├── messaging/              # Event bus + Celery
│   │   │   │   ├── event_bus.py        # Domain event dispatcher
│   │   │   │   ├── celery_app.py
│   │   │   │   └── task_handlers.py    # Maps domain events → Celery tasks
│   │   │   └── monitoring/
│   │   │       ├── health.py           # /health and /ready endpoints
│   │   │       └── metrics.py          # Prometheus-compatible metrics
│   │   │
│   │   └── api/v1/                     # Interface layer (thin HTTP → command/query mapping)
│   │       ├── auth.py, projects.py, connections.py
│   │       ├── discovery.py, masking.py, synthetic.py
│   │       ├── subsetting.py, workflows.py, jobs.py
│   │       ├── admin.py
│   │       └── events.py (SSE streaming)
│   │
│   └── tests/
│       ├── unit/                       # pytest — mirrors app/ structure
│       ├── integration/                # pytest + testcontainers
│       └── conftest.py                 # Shared fixtures, factory_boy factories
│
├── cli/                                # CLI tool (Phase 3)
│   ├── pyproject.toml
│   └── datawrangler/cli.py
│
└── docs/
    ├── architecture.md
    ├── api-reference.md
    └── getting-started.md
```

---

## Database Schema (Metadata Store — PostgreSQL)

### Core Tables

```sql
-- Users & Auth
users (id, email, full_name, role, sso_subject_id, sso_provider,
       is_active, created_at, updated_at)

-- Projects (top-level organizational unit)
projects (id, name, description, owner_id, settings JSONB, created_at, updated_at)

-- Data Connections (credentials encrypted with Fernet, key rotation supported)
connections (id, project_id, name, connector_type, host, port, database_name,
            credentials JSONB, extra_params JSONB, status, last_tested_at)

-- Schema Discovery
discovered_schemas (id, connection_id, schema_name, discovered_at)
discovered_tables (id, schema_id, table_name, row_count, size_bytes)
discovered_columns (id, table_id, column_name, data_type, is_nullable, is_primary_key,
                   is_foreign_key, fk_references JSONB, sample_values JSONB, stats JSONB,
                   pii_type, pii_confidence, pii_detector, classification JSONB)
discovered_relationships (id, schema_id, source_table_id, source_column_id,
                         target_table_id, target_column_id, relationship_type, confidence)

-- Masking
masking_policies (id, project_id, name, description, is_default)
masking_rules (id, policy_id, column_id, match_pattern JSONB, masking_type,
              masking_config JSONB, preserve_format, deterministic)

-- Synthetic Data
synthetic_configs (id, project_id, name, source_connection_id, target_connection_id,
                  tables JSONB, generation_method, config JSONB, nlp_prompt TEXT)

-- Subsetting
subset_configs (id, project_id, name, source_connection_id, target_connection_id,
               target_percentage, target_row_count, root_tables JSONB, traversal_strategy)

-- Workflows
workflows (id, project_id, name, description, dag_definition JSONB, schedule, is_active)

-- Jobs & Logs (with checkpoint support for idempotent resume)
jobs (id, project_id, job_type, reference_id, status, progress, checkpoint JSONB,
     started_at, completed_at, error_message, result_summary JSONB,
     celery_task_id, created_by, llm_token_count INTEGER)
job_logs (id, job_id, level, message, details JSONB, created_at)

-- Dead Letter Queue
dead_letter_jobs (id, original_job_id, job_type, payload JSONB, error_message,
                 retry_count, created_at, resolved_at, resolved_by)

-- Audit & Compliance
audit_logs (id, user_id, project_id, action, resource_type, resource_id,
           details JSONB, ip_address, created_at)
compliance_reports (id, project_id, report_type, regulation, generated_at,
                   data JSONB, storage_path, created_by)
```

---

## API Endpoints (REST, base: /api/v1)

| Area | Method | Endpoint | Description |
|------|--------|----------|-------------|
| **Auth** | GET | /auth/sso/login | Initiate SSO flow (OIDC/SAML) |
| | GET | /auth/sso/callback | SSO callback handler |
| | POST | /auth/token | Service account JWT token |
| | POST | /auth/refresh | Refresh token |
| **Health** | GET | /health | Liveness check |
| | GET | /ready | Readiness check (with dependency status) |
| **Projects** | GET/POST | /projects | List / Create |
| | GET/PUT/DELETE | /projects/{id} | Detail / Update / Delete |
| **Connections** | GET/POST | /projects/{pid}/connections | List / Create |
| | POST | /projects/{pid}/connections/{id}/test | Test connectivity |
| | GET | /projects/{pid}/connections/{id}/schemas | Live schema introspection |
| **Discovery** | POST | /projects/{pid}/discovery/run | Start discovery (async) |
| | GET | /projects/{pid}/discovery/results | Schema tree |
| | GET | /projects/{pid}/discovery/pii | PII classifications |
| | PUT | /projects/{pid}/discovery/columns/{id}/classification | Override PII |
| | GET | /projects/{pid}/discovery/relationships | Inferred relationships |
| **Masking** | GET/POST | /projects/{pid}/masking/policies | List / Create policies |
| | POST | /projects/{pid}/masking/policies/{id}/rules | Add rule |
| | POST | /projects/{pid}/masking/preview | Preview on sample |
| | POST | /projects/{pid}/masking/execute | Execute (async) |
| **Synthetic** | POST | /projects/{pid}/synthetic/configs | Create config |
| | POST | /projects/{pid}/synthetic/preview | Preview (sync, 10 rows) |
| | POST | /projects/{pid}/synthetic/generate | Generate (async) |
| | POST | /projects/{pid}/synthetic/nlp-generate | NLP prompt generation |
| | GET | /projects/{pid}/synthetic/{id}/quality | Quality evaluation score |
| **Subsetting** | POST | /projects/{pid}/subset/configs | Create config |
| | POST | /projects/{pid}/subset/analyze | Dry-run analysis |
| | POST | /projects/{pid}/subset/execute | Execute (async) |
| **Jobs** | GET | /projects/{pid}/jobs | List (filterable) |
| | GET | /projects/{pid}/jobs/{id} | Detail + logs |
| | POST | /projects/{pid}/jobs/{id}/cancel | Cancel |
| | POST | /projects/{pid}/jobs/{id}/retry | Retry from checkpoint |
| | GET | /projects/{pid}/jobs/{id}/stream | SSE real-time progress |
| **Workflows** | POST | /projects/{pid}/workflows | Create DAG |
| | POST | /projects/{pid}/workflows/{id}/execute | Execute workflow |
| **Compliance** | POST | /projects/{pid}/compliance/reports | Generate report (HIPAA/GDPR/CCPA) |
| | GET | /projects/{pid}/compliance/reports | List reports |
| | GET | /projects/{pid}/compliance/reports/{id}/download | Download PDF |
| **Admin** | POST | /admin/rotate-encryption-key | Re-encrypt all credentials with new Fernet key |
| | GET | /admin/dead-letter | List DLQ entries |
| | POST | /admin/dead-letter/{id}/retry | Retry DLQ job |

---

## AI Pipeline Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  Schema Discovery │────>│  PII Detection   │────>│ Relationship Inference│────>│  Data Generation │
│                  │     │                  │     │                      │     │                  │
│ - information_   │     │ - Regex patterns │     │ - Declared FKs       │     │ - Faker (fast)   │
│   schema queries │     │ - Presidio+spaCy │     │ - Naming conventions │     │ - Statistical    │
│ - Document       │     │ - Column name    │     │ - Value overlap      │     │   (copulas/ctgan)│
│   sampling       │     │   heuristics     │     │   analysis           │     │ - LLM (smart)    │
│ - Column stats   │     │ - LLM fallback   │     │ - LLM assistance     │     │                  │
│                  │     │   (conf < 0.4)   │     │                      │     │ NLP: "Generate   │
│ Confidence: 1.0  │     │ Weighted scoring │     │ Confidence scores    │     │  1000 claims..." │
└──────────────────┘     └──────────────────┘     └──────────────────────┘     └──────────────────┘
         │                        │                         │                          │
         └────────────────────────┴─────────────────────────┴──────────────────────────┘
                                          │
                              ┌────────────────────────┐
                              │   LLM Provider Layer    │
                              │ ┌──────┐  ┌──────────┐ │
                              │ │Claude│  │  Ollama   │ │
                              │ │ API  │  │(self-host)│ │
                              │ └──────┘  └──────────┘ │
                              │  Circuit breaker +      │
                              │  cost tracking          │
                              └────────────────────────┘
```

---

## SDV-Inspired Architecture (Build from Scratch)

DataWrangler's synthetic engine takes architectural inspiration from the SDV library (studied at `/Desktop/sdv`) but is built entirely from scratch with zero code dependency:

| SDV Pattern | DataWrangler Implementation |
|------------|---------------------------|
| Metadata auto-detection + JSON serialization | Own metadata system in `domain/discovery/entities.py` with PII-aware column types |
| `fit()`/`sample()` synthesizer pattern | `BaseSyntheticEngine` ABC with `train()`, `generate()`, `evaluate()` in `domain/synthetic/services.py` |
| HMA hierarchical multi-table synthesis | FK-aware generation with topological sort in `StatisticalEngine` |
| Constraint framework (CAG) | Business rule enforcement in `domain/synthetic/value_objects.py` — Range, Inequality, FixedCombinations |
| Quality evaluation (KS test, column metrics) | Quality scoring in `domain/synthetic/services.py` using scipy stats directly |
| Data processing pipeline | Preprocessing/postprocessing in `infrastructure/connectors/` with format-specific handlers |
| Plugin discovery (entry points) | Connector registration via entry points in `infrastructure/connectors/registry.py` |

**Underlying ML libraries used directly** (not through SDV):
- `copulas` — Gaussian copula synthesis
- `ctgan` — CTGAN and TVAE deep learning synthesis
- `deepecho` — Time series synthesis (if needed)
- `scipy.stats` — Statistical tests for quality evaluation

---

## Implementation Phases

### Phase 1: MVP (10 weeks)
- **Sprint 1-2**: Backend foundation (FastAPI, DDD structure, DI container, database, Alembic migrations) + SSO auth (OIDC/SAML) + PostgreSQL connector + Docker dev environment + test infrastructure (pytest, Jest, Playwright scaffolds) + LLM provider abstraction (Claude + Ollama)
- **Sprint 3-4**: Schema discovery engine + 4-layer PII detection pipeline + Faker synthetic engine + MySQL connector + Frontend foundation (Next.js, Ant Design, AppShell, SSO auth flow)
- **Sprint 5**: MongoDB + Snowflake connectors + Dashboard + project/connection pages + schema explorer UI + job monitoring + SSE streaming + storage abstraction (local FS default)

### Phase 2: Advanced Features (8 weeks)
- **Sprint 6-7**: Statistical synthetic engine (copulas/ctgan, built from scratch) + LLM synthetic engine (NLP prompt → generation plan → execution) + Masking engine (7 strategies + FPE) + Quality evaluation dashboard
- **Sprint 8-9**: Graph-aware subsetting engine + ReactFlow visual workflow builder + Workflow execution engine (Celery DAG runner) + Relationship graph visualization

### Phase 3: Enterprise (8 weeks)
- **Sprint 10-11**: HIPAA compliance report generator + GDPR compliance report generator + CCPA compliance report generator + RBAC (admin/editor/viewer per project) + Full audit trail
- **Sprint 12-13**: CLI tool (`datawrangler` command) + Webhooks + API key auth + Production Docker Compose + S3 storage backend option + Remaining connectors (Oracle, SQL Server, CSV, JSON, Parquet, Avro) — as capacity allows

---

## Docker Services

### Development (`docker-compose.dev.yml`)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| postgres | postgres:16 | 5432 | Metadata store |
| redis | redis:7-alpine | 6379 | Celery broker + cache + sessions |
| backend | Custom | 8000 | FastAPI (uvicorn --reload) |
| worker | Same as backend | — | Celery worker |
| frontend | Custom | 3000 | Next.js dev server |
| flower | mher/flower | 5555 | Celery monitoring |

### Production (`docker-compose.prod.yml`)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| postgres | postgres:16 | 5432 | Metadata store (external volume) |
| redis | redis:7-alpine | 6379 | Celery broker + cache + sessions |
| backend | Custom | 8000 | FastAPI (uvicorn, no reload) |
| worker | Same as backend | — | Celery worker (multiple replicas) |
| frontend | Custom | 3000 | Next.js production build |
| flower | mher/flower | 5555 | Celery monitoring |
| nginx | nginx:alpine | 80/443 | Reverse proxy + SSL termination |

**Production additions**: Resource limits, `unless-stopped` restart policies, external volume mounts, `.env.prod` configuration.

---

## Security

- **Auth**: SSO (SAML/OIDC) for users; JWT for service accounts and API keys
- **CORS**: Whitelist Ameritas domains only
- **Rate limiting**: slowapi on auth endpoints
- **Credentials**: Fernet encryption at rest; key from environment variable; rotation via admin API
- **Network**: Backend not publicly exposed; frontend proxies API calls through Nginx
- **Input validation**: Pydantic models on all endpoints; parameterized queries in all connectors
- **Audit**: Every API call logged with user, action, resource, timestamp, IP address

---

## Testing Strategy

| Layer | Tool | Scope | Coverage Target |
|-------|------|-------|----------------|
| Backend Unit | pytest + pytest-asyncio | Domain services, value objects, command handlers | 70% |
| Backend Integration | pytest + testcontainers | Repository implementations, connector operations, API endpoints | Key flows |
| Frontend Unit | Jest + React Testing Library | Components, hooks, stores | 60% |
| Frontend E2E | Playwright | Critical user workflows (create project → discover → mask → generate) | Happy paths |
| Fixtures | factory_boy | Consistent test data factories for all domain entities | — |

---

## Getting Started

```bash
# Clone and setup
cd ameritas-datawrangler
cp .env.example .env

# Start all services
make dev
# or: docker compose -f docker-compose.dev.yml up

# Access
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
# Flower: http://localhost:5555
```

---

## UI/UX Specification

### Design System

**Approach**: Hybrid — **shadcn/ui + Tailwind CSS** (primary) with **Ant Design v5** (isolated, for data-heavy components). 21st.dev component marketplace for polished UI blocks.

| Layer | Technology | Usage |
|-------|-----------|-------|
| **Primary UI** | shadcn/ui + Tailwind CSS + Radix UI | Layout, navigation, cards, buttons, forms, modals, drawers, AI chat, command palette |
| **Data Components** | Ant Design v5 Table, Tree (CSS-scoped) | Schema explorer tree, PII results table, job logs table, audit trail — isolated via CSS Modules |
| **Charts** | Recharts | Distribution comparisons, quality scores, donut charts, heatmaps |
| **Graph Viz** | ReactFlow | Workflow builder, relationship graph, subsetting dependency graph |
| **21st.dev** | shadcn components (copy-paste) | AI chat interface, dashboard layouts, command palette, stat cards, animated counters |
| **Icons** | Lucide React | Consistent icon set across all components |

**CSS Scoping Strategy**: Ant Design components wrapped in CSS Module containers (`.ant-scoped`) to prevent Tailwind conflicts. Ant theme tokens synced to CSS variables for consistent theming.

#### Theme Tokens (CSS Variables)

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--primary` | `#1B65A6` (Ameritas Blue) | `#4A9AE6` | Primary actions, active navigation, links |
| `--success` | `#22C55E` | `#4ADE80` | Healthy connections, completed jobs |
| `--warning` | `#F59E0B` | `#FBBF24` | Needs-review PII, in-progress jobs |
| `--destructive` | `#EF4444` | `#F87171` | Failed jobs, errors, high-confidence PII |
| `--background` | `#F5F7FA` | `#0A0A0F` | Page background |
| `--card` | `#FFFFFF` | `#111118` | Cards, panels, modals |
| `--foreground` | `#0F172A` | `#F1F5F9` | Primary text |
| `--muted` | `#64748B` | `#94A3B8` | Secondary text, placeholders |
| `--border` | `#E2E8F0` | `#1E293B` | Borders, dividers |
| `--radius` | `8px` | `8px` | Cards, buttons, inputs |

**Typography**: `'Inter', -apple-system, sans-serif` (UI) / `'JetBrains Mono', monospace` (code, SQL, column names)
**Spacing**: 4px base unit (4, 8, 12, 16, 24, 32, 48, 64)
**Breakpoints**: Mobile (< 768px), Tablet (768-1024px), Desktop (> 1024px), Wide (> 1440px)

#### Theme Modes
Three-way toggle in header: **Light / Dark / System**
- System mode auto-detects OS preference via `prefers-color-scheme`
- CSS variables switch all tokens; no page reload
- User preference persisted in localStorage
- Ant Design components synced via `ConfigProvider` theme token override

---

### Application Shell

```
┌───────────────────────────────────────────────────────────────────────┐
│  [Logo]  DataWrangler    [⌘K Search]    [🌓Theme] [🔔Notif] [Avatar] │
├────────┬──────────────────────────────────────────────────────────────┤
│        │                                                        │
│  NAV   │                    CONTENT AREA                        │
│        │                                                        │
│ Home   │  ┌─────────────────────────────────────────────────┐  │
│ Projects│  │  Breadcrumb: Home > Project X > Discovery       │  │
│ Admin  │  ├─────────────────────────────────────────────────┤  │
│        │  │                                                 │  │
│ ────── │  │  Page-specific content with consistent          │  │
│ Current│  │  padding, max-width, and card-based layout      │  │
│ Project│  │                                                 │  │
│ ────── │  │                                                 │  │
│ Connect│  │                                                 │  │
│ Discov │  │                                                 │  │
│ Masking│  │                                                 │  │
│ Synth  │  │                                                 │  │
│ Subset │  │                                                 │  │
│ Workflw│  │                                                 │  │
│ Jobs   │  │                                                 │  │
│ Compli │  └─────────────────────────────────────────────────┘  │
│        │                                                        │
└────────┴────────────────────────────────────────────────────────┘
```

- **Sidebar**: 240px collapsed to 64px (icon-only). Collapsible with hamburger or keyboard shortcut. Top section: global nav. Bottom section: project-scoped nav (appears after selecting a project). Active item highlighted with left border + background.
- **Header**: 56px height. Logo left, global search center (Cmd+K), theme toggle (Light/Dark/System), notification center bell with unread count badge, user avatar/dropdown right.
- **Content**: Max-width 1440px, centered. 24px padding. Breadcrumb navigation at top.
- **Responsive**: Sidebar becomes drawer on tablet/mobile. Content goes full-width.

---

### Page Specifications

#### 1. Dashboard (`/`)

```
┌──────────────────────────────────────────────────────────────┐
│  Welcome back, {name}                              [+ New Project] │
├──────────┬──────────┬──────────┬────────────────────────────┤
│ STAT     │ STAT     │ STAT     │ STAT                       │
│ 12       │ 3        │ 847      │ 23                         │
│ Projects │ Active   │ Tables   │ Jobs Today                 │
│          │ Jobs     │ Masked   │                            │
├──────────┴──────────┴──────────┴────────────────────────────┤
│                                                              │
│  Recent Projects                              [View All →]   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Project A    │ │ Project B    │ │ Project C    │        │
│  │ 12 tables    │ │ 8 tables     │ │ 24 tables    │        │
│  │ 96% masked   │ │ 45% masked   │ │ Not started  │        │
│  │ Last: 2h ago │ │ Last: 1d ago │ │ Last: 3d ago │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                              │
│  Active Jobs                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ [████████░░] 78%  Discovery — Project A — 2m left    │   │
│  │ [██████████] Done Masking — Project B — Completed     │   │
│  │ [██░░░░░░░░] 15%  Generation — Project A — 8m left   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  PII Coverage                                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ [Donut Chart]  Detected: 234 │ Masked: 198 │ Pending: 36│
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

- **Stat cards**: Clickable, navigate to relevant section
- **Project cards**: Hover elevation, click navigates to project
- **Job progress**: Real-time via SSE, animated progress bars
- **PII donut chart**: Recharts donut with animated counter from 21st.dev

#### 2. Project List (`/projects`)

- **Table view** (default) with columns: Name, Owner, Connections, Tables Discovered, PII Coverage %, Last Activity, Actions
- **Card view** toggle for visual overview
- **Filters**: Owner, date range, PII coverage status
- **Sort**: Name, last activity, PII coverage
- **Search**: Real-time filter by project name
- **Empty state**: Illustrated placeholder with "Create your first project" CTA
- **Bulk actions**: Archive, delete (with confirmation modal)

#### 3. Connection Management (`/projects/{id}/connections`)

```
┌──────────────────────────────────────────────────────────────┐
│  Connections                              [+ Add Connection]  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ [PostgreSQL Icon]  Production Replica                │     │
│  │ postgres://db-prod.ameritas.internal:5432/claims     │     │
│  │ Status: ● Connected    Last tested: 5 min ago        │     │
│  │                              [Test] [Edit] [Delete]  │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ [Snowflake Icon]  Analytics Warehouse                │     │
│  │ ameritas.snowflakecomputing.com / ANALYTICS_DB       │     │
│  │ Status: ● Connected    Last tested: 1 hour ago       │     │
│  │                              [Test] [Edit] [Delete]  │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

- **Connection Form**: Slide-in drawer from right (480px width)
  - Connector type selector with icons (PostgreSQL, MySQL, MongoDB, Snowflake, etc.)
  - Dynamic form fields based on connector type
  - Credential fields masked by default with show/hide toggle
  - "Test Connection" button with inline success/failure feedback
  - Advanced options collapsible section (SSL, SSH tunnel, extra params)
- **Status indicators**: Green dot (connected), yellow dot (untested), red dot (failed), gray dot (disabled)
- **Connection detail**: Click to expand showing last 5 test results and connection metadata

#### 4. Schema Discovery (`/projects/{id}/discovery`)

```
┌──────────────────────────────────────────────────────────────┐
│  Schema Discovery                     [Run Discovery ▼]       │
│  Connection: Production Replica       [Full] [Incremental]    │
├─────────────────────┬────────────────────────────────────────┤
│  SCHEMA TREE        │  COLUMN DETAIL                          │
│                     │                                          │
│  ▼ public           │  Table: users (12,847 rows)              │
│    ▼ users          │  ┌──────────────────────────────────┐   │
│      id             │  │ Column: email                     │   │
│      email      ●   │  │ Type: VARCHAR(255)                │   │
│      full_name  ●   │  │ Nullable: No                      │   │
│      ssn        ●   │  │ Unique: Yes                       │   │
│      phone      ●   │  │ Null %: 0%                        │   │
│      address    ●   │  │ Cardinality: 12,847               │   │
│      created_at     │  │                                    │   │
│    ▼ claims         │  │ PII Detection                      │   │
│      id             │  │ ┌──────────────────────────────┐  │   │
│      user_id    🔗  │  │ │ ● EMAIL — Confidence: 0.98   │  │   │
│      amount         │  │ │ Detected by: Regex + Presidio│  │   │
│      type           │  │ │ [Auto-classified]             │  │   │
│      filed_at       │  │ │            [Override ▼]       │  │   │
│    ▶ policies       │  │ └──────────────────────────────┘  │   │
│    ▶ payments       │  │                                    │   │
│                     │  │ Sample Values (masked)             │   │
│  ▶ analytics        │  │ j***@email.com                     │   │
│                     │  │ m***@ameritas.com                  │   │
│                     │  │ s***@gmail.com                     │   │
│  Legend:            │  └──────────────────────────────────┘   │
│  ● PII detected    │                                          │
│  🔗 Foreign key    │                                          │
└─────────────────────┴────────────────────────────────────────┘
```

- **Schema tree**: Collapsible tree with search/filter. PII columns marked with colored dots (red = high confidence, yellow = needs review). FK columns marked with link icon.
- **Column detail panel**: Click any column in tree to show detail. Includes data type, stats, PII classification with confidence, detector breakdown, sample values (auto-masked in display).
- **PII override**: Dropdown to manually classify/reclassify with audit note.
- **Bulk actions**: "Auto-mask all high-confidence PII" button.
- **Discovery progress**: When running, show per-table progress with estimated time.

#### 5. PII Results (`/projects/{id}/discovery/pii`)

- **Table view**: All columns with PII detections. Columns: Table, Column, PII Type, Confidence, Detector, Classification Status, Actions.
- **Classification badges**: Color-coded by confidence (green = auto-classified >=0.65, yellow = needs review 0.4-0.65, red = high-risk PII types like SSN/CC)
- **Filters**: By PII type, confidence range, classification status (auto/manual/pending), table
- **Bulk classify**: Select multiple → batch classify/dismiss
- **Export**: CSV download of all PII findings for compliance documentation

#### 6. Masking (`/projects/{id}/masking`)

**Policy List View:**
- Cards showing policy name, description, rule count, last applied date
- Default policy badge
- Click to expand rules

**Rule Editor (Drawer):**
```
┌──────────────────────────────────────────────────────┐
│  Add Masking Rule                                [X]  │
│                                                      │
│  Target Column                                       │
│  [Table ▼] [Column ▼]  or  [Match by PII Type ▼]    │
│                                                      │
│  Masking Strategy                                    │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │  Hash  │ │ Redact │ │ Faker  │ │Shuffle │       │
│  └────────┘ └────────┘ └────────┘ └────────┘       │
│  ┌────────┐ ┌────────┐                              │
│  │Nullify │ │  FPE   │                              │
│  └────────┘ └────────┘                              │
│                                                      │
│  Options                                             │
│  ☑ Preserve format                                   │
│  ☑ Deterministic (same input → same output)          │
│                                                      │
│  Preview                                             │
│  ┌────────────────────────────────────────────┐     │
│  │ Original          │ Masked                  │     │
│  │ john@email.com    │ 7a3f@email.com          │     │
│  │ 555-123-4567      │ 555-***-****            │     │
│  │ John Smith        │ Robert Johnson          │     │
│  └────────────────────────────────────────────┘     │
│                                                      │
│                          [Cancel]  [Save Rule]       │
└──────────────────────────────────────────────────────┘
```

- **Strategy cards**: Visual selector with icon + description for each strategy
- **Live preview**: Shows 5 sample rows with before/after as you configure
- **FPE config**: Additional fields for algorithm selection (FF1/FF3-1), alphabet

#### 7. Synthetic Data Generation (`/projects/{id}/synthetic`)

**Engine Selector:**
```
┌──────────────────────────────────────────────────────────────┐
│  Generate Synthetic Data                                      │
│                                                              │
│  Choose Engine:                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   ⚡ Faker   │  │ 📊 Statist. │  │ 🧠 LLM      │         │
│  │   Fast       │  │ Accurate    │  │ Intelligent  │         │
│  │   ~1K/sec    │  │ ~100/sec    │  │ ~10/sec      │         │
│  │   Basic      │  │ Preserves   │  │ NLP prompt   │         │
│  │   patterns   │  │ distributions│  │ driven       │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└──────────────────────────────────────────────────────────────┘
```

**NLP Prompt Interface (LLM Engine):**
```
┌──────────────────────────────────────────────────────────────┐
│  Describe the data you need:                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Generate 5000 insurance claims where:                  │   │
│  │ - 60% are health claims, 30% auto, 10% property       │   │
│  │ - Amounts follow realistic distributions ($200-$500K)  │   │
│  │ - 15% are flagged as suspicious                        │   │
│  │ - All have valid policyholder references                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                               [Generate Plan]│
│                                                              │
│  Generation Plan (editable):                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Table: claims                                          │   │
│  │ Rows: 5,000                                            │   │
│  │ Column Configs:                                        │   │
│  │   claim_type: categorical(health=60%, auto=30%,        │   │
│  │               property=10%)                            │   │
│  │   amount: lognormal(mean=5000, std=15000,              │   │
│  │           min=200, max=500000)                         │   │
│  │   is_suspicious: boolean(true=15%)                     │   │
│  │   policyholder_id: fk(policyholders.id)                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Preview (10 rows):                                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ claim_type │ amount    │ suspicious │ policyholder_id │   │
│  │ health     │ $3,245.00 │ No         │ POL-00847       │   │
│  │ auto       │ $12,100   │ Yes        │ POL-01203       │   │
│  │ health     │ $890.50   │ No         │ POL-00291       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                     [Edit Plan] [Generate →] │
└──────────────────────────────────────────────────────────────┘
```

- **Quality Score**: After generation, show quality evaluation (0-100) with distribution comparison charts
- **Statistical Engine Config**: Model selector (GaussianCopula, CTGAN), hyperparameters, training time estimate
- **Multi-table**: Visual indicator of generation order (topological sort visualization)

#### 8. Subsetting (`/projects/{id}/subsetting`)

```
┌──────────────────────────────────────────────────────────────┐
│  Data Subsetting                                              │
│                                                              │
│  Root Table: [claims ▼]     Traversal: [Upstream ▼]          │
│  Filter: [WHERE filed_at > '2024-01-01' AND type = 'auto']  │
│  Target: [10] % of data     ≈ 1,284 rows from root           │
│                                                              │
│  [Analyze (Dry Run)]                                          │
│                                                              │
│  Dependency Graph:                                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         policyholders (2,847)                         │   │
│  │              │                                        │   │
│  │         ┌────┴────┐                                   │   │
│  │    claims (1,284)  policies (2,847)                   │   │
│  │         │                                             │   │
│  │    payments (3,412)                                   │   │
│  │                                                       │   │
│  │  Total: 10,390 rows across 4 tables                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Table Breakdown:                                             │
│  │ Table          │ Full Count │ Subset Count │ %       │    │
│  │ policyholders  │ 28,470     │ 2,847        │ 10.0%   │    │
│  │ claims         │ 12,847     │ 1,284        │ 10.0%   │    │
│  │ policies       │ 28,470     │ 2,847        │ 10.0%   │    │
│  │ payments       │ 34,120     │ 3,412        │ 10.0%   │    │
│  │ TOTAL          │ 103,907    │ 10,390       │ 10.0%   │    │
│                                                              │
│                                       [Execute Subset →]     │
└──────────────────────────────────────────────────────────────┘
```

- **Interactive dependency graph**: Zoomable, pannable. Nodes show table name + row count. Edges show FK relationships.
- **Dry-run table**: Sortable, shows impact before execution
- **Traversal toggle**: Visual arrows change direction on the graph

#### 9. Visual Workflow Builder (`/projects/{id}/workflows`)

```
┌──────────────────────────────────────────────────────────────┐
│  Workflow: Nightly Data Refresh            [Save] [Run ▶]    │
│  Schedule: 0 2 * * * (Daily 2 AM)          [Enabled ✓]      │
├──────────┬───────────────────────────────────────────────────┤
│ NODE     │                                                    │
│ PALETTE  │         ┌──────────┐     ┌──────────┐            │
│          │         │ Discover │────→│   Mask   │            │
│ ┌──────┐ │         │ ✓ Done   │     │ ⟳ Running│            │
│ │Discov│ │         └──────────┘     └────┬─────┘            │
│ └──────┘ │                               │                    │
│ ┌──────┐ │                          ┌────▼─────┐            │
│ │ Mask │ │                          │ Generate │            │
│ └──────┘ │                          │ ○ Pending│            │
│ ┌──────┐ │                          └────┬─────┘            │
│ │Genera│ │                               │                    │
│ └──────┘ │    ┌──────────┐          ┌────▼─────┐            │
│ ┌──────┐ │    │  Subset  │────→     │  Export  │            │
│ │Subset│ │    │ ○ Pending│          │ ○ Pending│            │
│ └──────┘ │    └──────────┘          └──────────┘            │
│ ┌──────┐ │                                                    │
│ │Export│ │  Click any node to configure ↓                     │
│ └──────┘ │  ┌──────────────────────────────────────────────┐ │
│          │  │ Node: Mask                                     │ │
│          │  │ Policy: [Default Masking Policy ▼]             │ │
│          │  │ Tables: [All discovered ▼]                     │ │
│          │  │ Batch size: [10000]                            │ │
│          │  └──────────────────────────────────────────────┘ │
├──────────┴───────────────────────────────────────────────────┤
│  Run History                                                  │
│  │ Run #12 │ 2024-03-15 02:00 │ ✓ Completed │ 12m 34s │    │
│  │ Run #11 │ 2024-03-14 02:00 │ ✗ Failed    │ 8m 12s  │    │
│  │ Run #10 │ 2024-03-13 02:00 │ ✓ Completed │ 11m 56s │    │
└──────────────────────────────────────────────────────────────┘
```

- **Node palette**: Drag nodes onto canvas. Each node type has distinct color and icon.
- **Node states**: Gray (pending), blue (running with spinner), green (completed), red (failed)
- **Edge validation**: Prevent invalid connections (e.g., Export before Discover)
- **Config panel**: Bottom drawer, context-sensitive to selected node
- **Run history**: Expandable rows showing per-node timing and errors

#### 10. Job Monitor (`/projects/{id}/jobs`)

```
┌──────────────────────────────────────────────────────────────┐
│  Jobs                              [Filter ▼] [Search]        │
├──────────────────────────────────────────────────────────────┤
│ │ Type       │ Status        │ Progress │ Started   │ Duration│
│ │ Discovery  │ ✓ Completed   │ 100%     │ 10:23 AM  │ 2m 14s │
│ │ Masking    │ ⟳ Running     │ 78%      │ 10:26 AM  │ 1m 32s │
│ │ Generation │ ○ Queued      │ 0%       │ —         │ —      │
│ │ Discovery  │ ✗ Failed      │ 45%      │ Yesterday │ 3m 01s │
├──────────────────────────────────────────────────────────────┤
│  Job Detail: Masking — Run #47                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ [████████████████████░░░░░░] 78% — Processing claims  │   │
│  │                                                       │   │
│  │ Tables:                                               │   │
│  │   ✓ users          — 12,847/12,847 rows (100%)        │   │
│  │   ✓ policyholders  — 28,470/28,470 rows (100%)        │   │
│  │   ⟳ claims         — 7,234/12,847 rows (56%)          │   │
│  │   ○ payments       — 0/34,120 rows (queued)            │   │
│  │                                                       │   │
│  │ Log:                                                  │   │
│  │  10:26:01 INFO  Starting masking job #47               │   │
│  │  10:26:02 INFO  Processing table: users (12,847 rows)  │   │
│  │  10:26:15 INFO  Table users complete (13s)             │   │
│  │  10:26:16 INFO  Processing table: policyholders        │   │
│  │  10:27:01 INFO  Table policyholders complete (45s)     │   │
│  │  10:27:02 INFO  Processing table: claims               │   │
│  │  10:27:33 INFO  Chunk 1/2 complete (7,234 rows)        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                         [Cancel] [Retry]     │
└──────────────────────────────────────────────────────────────┘
```

- **Real-time updates**: SSE streaming for progress bars and log lines
- **Per-table breakdown**: Shows completion per table within a job
- **Log viewer**: Auto-scrolling, filterable by level (INFO/WARN/ERROR), searchable
- **Failed jobs**: Show error message prominently with "Retry from checkpoint" button

#### 11. Compliance Reports (`/projects/{id}/compliance`)

- **Report generation form**: Select regulation (HIPAA/GDPR/CCPA), date range, scope (all tables or selected)
- **Report list**: Name, regulation type, generated date, generated by, download button
- **Report preview**: In-browser PDF viewer for quick review before download
- **PII coverage dashboard**: Donut chart (detected/masked/pending), table-level heatmap

#### 12. Admin Panel (`/admin`)

- **User management**: List users, roles, SSO status, last login
- **Dead letter queue**: List failed jobs, error details, retry/dismiss actions
- **Encryption key rotation**: One-click rotation with progress indicator
- **System health**: Service status cards (PostgreSQL, Redis, Celery workers, LLM providers)
- **Audit log**: Filterable table of all actions (user, action, resource, timestamp, IP)

---

### UX Patterns

#### Loading States
- **Skeleton screens**: For initial page loads (Ant Design Skeleton)
- **Inline spinners**: For actions within loaded pages
- **Progress bars**: For long-running async operations (jobs)
- **Optimistic updates**: For quick actions (toggle, delete) — update UI immediately, revert on error

#### Empty States
Every list/table has a designed empty state with:
- Illustration (custom SVG or Ant Design Empty)
- Title explaining what belongs here
- Description with getting-started guidance
- Primary CTA button (e.g., "Add your first connection")

#### Error States
- **Inline errors**: Form validation shown inline below fields (Ant Design Form validation)
- **Toast notifications**: Success/error toasts for async operations (Ant Design message)
- **Error boundaries**: Catch React errors with "Something went wrong" fallback + retry
- **API errors**: Structured error display with error code, message, and suggested action

#### Confirmation Patterns
- **Destructive actions**: Require typed confirmation (e.g., type project name to delete)
- **Irreversible bulk actions**: Warning modal with item count and explicit confirmation
- **Job cancellation**: Confirm with warning about partial results

#### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Cmd+K` | Global search |
| `Cmd+N` | New (context-dependent: project, connection, etc.) |
| `Cmd+S` | Save current form |
| `Escape` | Close drawer/modal |
| `?` | Show keyboard shortcut help |

#### Accessibility
- WCAG 2.1 AA compliance target
- All interactive elements keyboard-navigable
- ARIA labels on icons and non-text elements
- Color not used as sole indicator (icons + text accompany color coding)
- Focus trapping in modals and drawers
- Screen reader announcements for async state changes (job progress, notifications)

---

### Data Visualization Components

| Component | Library | Usage |
|-----------|---------|-------|
| **Relationship Graph** | ReactFlow or D3.js | FK dependency visualization, zoomable/pannable |
| **Schema Tree** | Ant Design Tree | Collapsible schema explorer with custom node rendering |
| **Distribution Charts** | Recharts or Ant Design Charts | Column distribution comparison (real vs. synthetic) |
| **PII Heatmap** | Custom CSS grid | Table-level PII coverage visualization |
| **Progress Donut** | Ant Design Progress | PII coverage, job progress summary |
| **Workflow Canvas** | ReactFlow | Drag-and-drop DAG builder with custom node types |
| **Log Viewer** | Custom virtualized list | Auto-scrolling, syntax-highlighted job logs |
| **Data Tables** | Ant Design Table (CSS-scoped) | Sortable, filterable, paginated with virtual scrolling for large datasets |

---

### Competitor-Informed Features (Gaps Filled)

Based on analysis of Delphix, Tonic.ai, Gretel.ai, MOSTLY AI, Databricks, Snowflake Snowsight, dbt Cloud, Airbyte, Collibra, and Immuta:

#### 1. AI Assistant (Inspired by: MOSTLY AI, Immuta Copilot, Databricks Genie)

A conversational AI sidebar available on every page — not just for synthetic generation, but for ALL platform operations.

```
┌──────────────────────────────────────────────────────┐
│  🤖 DataWrangler Assistant                    [—] [X] │
├──────────────────────────────────────────────────────┤
│                                                      │
│  You: "Which tables have unmasked PII?"              │
│                                                      │
│  Assistant: Found 4 tables with unmasked PII:        │
│  • users — 3 columns (email, ssn, phone)             │
│  • claims — 1 column (claimant_name)                 │
│  • payments — 2 columns (card_number, billing_addr)  │
│  • contacts — 2 columns (mobile, address)            │
│                                                      │
│  [Auto-mask all with default policy]                 │
│  [Show details]                                      │
│                                                      │
│  You: "Generate 10K claims matching last month's     │
│  distribution but with 5% fraud rate"                │
│                                                      │
│  Assistant: I'll create a generation plan:            │
│  • Source: claims table (Dec 2025 distribution)      │
│  • Engine: Statistical (GaussianCopula)              │
│  • Override: is_fraud = boolean(true=5%)             │
│  • Rows: 10,000                                      │
│                                                      │
│  [Execute] [Edit plan] [Show SQL]                    │
│                                                      │
├──────────────────────────────────────────────────────┤
│  [Ask anything about your data...]          [Send ▶] │
└──────────────────────────────────────────────────────┘
```

- **Capabilities**: Query PII status, create masking rules, generate data, explain schemas, suggest subsetting strategies, check job status, generate compliance reports
- **Context-aware**: Knows which project/page the user is on; suggestions are scoped
- **Action buttons**: Every response includes actionable CTAs that execute platform operations
- **Component source**: 21st.dev AI Chat components (78 available) — use "Glowing AI Chat Assistant" or similar
- **Resizable**: Dockable right panel or floating overlay, collapsible to icon

#### 2. Synthetic Data Quality Visualization (Inspired by: Gretel SQS, MOSTLY AI QA Reports)

Neither Delphix nor basic tools show quality metrics. Gretel and MOSTLY AI lead here.

```
┌──────────────────────────────────────────────────────────────┐
│  Quality Report — claims (GaussianCopula, 10K rows)          │
│  Overall Score: 92/100  [████████████████████░░] Excellent    │
│                                                              │
│  ┌─────────────────────┬─────────────────────────────────┐  │
│  │ Sub-Metric          │ Score                            │  │
│  │ Column Shapes       │ 95% ████████████████████░        │  │
│  │ Column Pairs        │ 88% ██████████████████░░░        │  │
│  │ Coverage            │ 94% ███████████████████░░        │  │
│  │ Boundaries          │ 91% ██████████████████░░░        │  │
│  │ Privacy (DCR)       │ 98% ████████████████████░        │  │
│  └─────────────────────┴─────────────────────────────────┘  │
│                                                              │
│  Distribution Comparison (click column to view):             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  claim_amount — 97% match                             │   │
│  │  ▓▓▓▓▓▓▓▓ Real (black)                               │   │
│  │  ░░░░░░░░ Synthetic (blue overlay)                    │   │
│  │  [Histogram showing overlaid distributions]            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Correlation Heatmap Triplet:                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Original   │  │  Synthetic  │  │ Difference  │            │
│  │  ██░░██░░█ │  │  ██░░██░░█ │  │  ░░░░░░░░░ │            │
│  │  ░░██░░██░ │  │  ░░██░░██░ │  │  ░░░░░░░░░ │            │
│  │  ██░░██░░█ │  │  ██░░██░░█ │  │  ░░░░░░░░░ │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│   (hover any cell to see correlation value)                  │
│                                                              │
│  Privacy Metrics:                                            │
│  • Distance to Closest Record (DCR): 0.23 avg               │
│  • Nearest Neighbor Distance Ratio (NNDR): 0.87 avg         │
│  • Identical Matches: 0 (0.00%)                              │
│                                                              │
│                           [Download Report PDF] [Share]      │
└──────────────────────────────────────────────────────────────┘
```

- **Composite quality score** (0-100) with sub-metrics breakdown
- **Overlaid distribution charts**: Real (black/dark) vs Synthetic (colored overlay) per column, with match percentage
- **Correlation heatmap triplets**: Original / Synthetic / Difference side-by-side with hover interactivity
- **Privacy metrics**: DCR, NNDR, identical matches count — proves synthetic data doesn't leak real records
- **Per-column drill-down**: Click any column to see detailed distribution comparison
- **Downloadable/shareable**: PDF export for stakeholder review

#### 3. Notification Center (Inspired by: Collibra, Snowflake)

Replace simple toast notifications with a centralized notification system.

```
┌──────────────────────────────────────────┐
│  Notifications                    [Mark all read] │
│  ┌────────────────────────────────────┐  │
│  │ 🔵 Discovery completed — Project A │  │
│  │    12 tables, 47 PII columns found │  │
│  │    2 minutes ago                   │  │
│  ├────────────────────────────────────┤  │
│  │ 🔴 Masking failed — Project B      │  │
│  │    Timeout on claims table         │  │
│  │    [Retry] [View Error]            │  │
│  │    15 minutes ago                  │  │
│  ├────────────────────────────────────┤  │
│  │ 🟢 Generation complete — Project A │  │
│  │    10,000 rows, Quality: 92/100    │  │
│  │    1 hour ago                      │  │
│  └────────────────────────────────────┘  │
│                                          │
│  Preferences:                            │
│  ☑ In-app    ☑ Email    ☐ Slack          │
│  Digest: [Instant ▼]                     │
└──────────────────────────────────────────┘
```

- **In-app inbox**: Bell icon with unread count badge, dropdown panel with notification list
- **Multi-channel**: In-app + email + Slack/Teams webhook (configurable per user)
- **Digest options**: Instant, hourly, daily summary
- **Actionable**: Each notification has contextual actions (Retry, View, Navigate)
- **Filterable**: By type (jobs, PII, compliance, system), by project

#### 4. Inline Collaboration (Inspired by: Snowflake Snowsight, Collibra)

Comments, annotations, and @mentions on TDM assets.

- **Column-level comments**: On any discovered column in the schema explorer — discuss PII classification, masking strategy decisions
- **@mentions**: Tag team members in comments, triggers notification
- **Masking rule discussions**: Comment thread on masking policies explaining why a strategy was chosen
- **Workflow annotations**: Notes on workflow nodes explaining configuration rationale
- **Compliance notes**: Auditor-facing annotations on compliance report items
- **Activity feed**: Per-project activity stream showing who did what and when

#### 5. Progressive Disclosure Configuration (Inspired by: Airbyte UX Handbook)

All configuration forms follow the Airbyte pattern:

- **Minimize visible fields**: Show only essential fields by default
- **Smart defaults**: 95% of users should be able to proceed without touching advanced settings
- **"Advanced" toggle**: Collapsible section for power users
- **Every field has help text**: Purpose + impact description via tooltip
- **Fail-fast validation**: Inline validation as user types, not on submit
- **Connection test on save**: Always test before persisting (no saving broken configs)

#### 6. Guided Onboarding Wizard (Inspired by: Tonic.ai, Airbyte)

First-time users see a 5-step wizard that walks them through creating their first complete TDM workflow:

```
Step 1: Create Project        ●───○───○───○───○
Step 2: Add Connection         ○───●───○───○───○
Step 3: Run Discovery          ○───○───●───○───○
Step 4: Review PII             ○───○───○───●───○
Step 5: Apply Masking          ○───○───○───○───●
```

- **Contextual**: Steps highlight the relevant UI area
- **Skippable**: "Skip tour" always available
- **Resumable**: Tracks progress, shows checklist in sidebar bottom
- **First value fast**: User has a working masked dataset within 15 minutes
- **Don't show again**: Preference toggle in user settings

#### 7. Side-by-Side Data Preview (Inspired by: Tonic.ai Privacy Hub)

All data transformation operations (masking, generation) show original vs. transformed data side-by-side:

```
┌──────────────────────────┬──────────────────────────┐
│  Original Data           │  Transformed Data         │
├──────────────────────────┼──────────────────────────┤
│ John Smith               │ Robert Chen              │
│ john.smith@ameritas.com  │ r.chen@example.com       │
│ 555-123-4567             │ 555-***-****             │
│ 123 Main St, Lincoln NE  │ 456 Oak Ave, Omaha NE    │
│ 402-78-1234              │ XXX-XX-XXXX              │
├──────────────────────────┼──────────────────────────┤
│ Jane Doe                 │ Michael Park             │
│ jane.doe@ameritas.com    │ m.park@example.com       │
│ 555-987-6543             │ 555-***-****             │
│ 456 Elm St, Omaha NE     │ 789 Pine Dr, Lincoln NE  │
│ 402-89-5678              │ XXX-XX-XXXX              │
└──────────────────────────┴──────────────────────────┘
  Showing 5 of 12,847 rows     [← Prev] [Next →]
```

- **Column slide-out**: Click any column header to see settings, sample data, and comments (3 tabs — like Tonic)
- **Color diff**: Changed values highlighted with subtle background color
- **Confidence indicators**: PII detection confidence shown per cell in discovery view

#### 8. Sensitive Data Heatmap (Inspired by: Delphix Data Control Tower)

Visual heatmap showing PII density across the entire schema:

```
┌──────────────────────────────────────────────────────────────┐
│  PII Heatmap — All Tables                    Legend:          │
│                                              ████ High (>80%) │
│  ┌──────────┬──────────┬──────────┐         ▓▓▓▓ Med (40-80%)│
│  │ users    │ claims   │ payments │         ░░░░ Low (<40%)   │
│  │ ████████ │ ▓▓▓▓░░░░ │ ████▓▓░░ │         ○○○○ None        │
│  │ 8/10 PII │ 3/12 PII │ 4/8 PII  │                          │
│  │ 2 unmskd │ 1 unmskd │ 0 unmskd │                          │
│  └──────────┴──────────┴──────────┘                          │
│  ┌──────────┬──────────┬──────────┐                          │
│  │ policies │ contacts │ logs     │                          │
│  │ ░░░░○○○○ │ ████████ │ ○○○○○○○○ │                          │
│  │ 1/15 PII │ 6/8 PII  │ 0/6 PII  │                          │
│  │ 0 unmskd │ 3 unmskd │ —        │                          │
│  └──────────┴──────────┴──────────┘                          │
│                                                              │
│  Click any table to drill into column-level detail           │
└──────────────────────────────────────────────────────────────┘
```

- **Grid layout**: Each cell = one table, color intensity = PII density
- **Unmasked count**: Prominently shows how many PII columns still need masking
- **Click to drill down**: Navigate to table-level PII detail
- **Cross-project view**: Admin can see heatmap across all projects

#### 9. Job Timeline / Gantt View (Inspired by: Tonic.ai)

Alternative to the list view for job monitoring — shows temporal overlap and dependencies:

```
┌──────────────────────────────────────────────────────────────┐
│  Job Timeline — Last 24 Hours                  [List] [Gantt] │
│                                                              │
│  10:00    10:30    11:00    11:30    12:00                    │
│  ├────────┼────────┼────────┼────────┤                       │
│  │ ██████████████░░░░░░░░░░░░░░░░░░│  Discovery (45m)       │
│  │        │ ████████████████████░░░░│  Masking (52m)         │
│  │        │        │ ██████████████ │  Generation (38m)      │
│  │        │        │        ████████│  Subset (25m)          │
│  │        │        │        │       │                        │
│  ├────────┼────────┼────────┼───────┤                        │
│  Legend: ██ Running  ░░ Queued  ▓▓ Retry                     │
└──────────────────────────────────────────────────────────────┘
```

- **Toggle**: Switch between list view and Gantt timeline view
- **Dependency arrows**: Show which jobs triggered others
- **Zoom**: Adjustable time scale (1h, 6h, 24h, 7d)

#### 10. Dual-Mode Interface (Inspired by: Airbyte, dbt Cloud)

For power users, offer code/expression editors alongside visual builders:

- **Masking rules**: Visual form editor OR YAML/JSON definition — toggle between modes, changes sync bidirectionally
- **Workflow definitions**: ReactFlow visual builder OR JSON DAG definition
- **Subsetting filters**: Form-based filter builder OR raw SQL WHERE clause
- **Synthetic config**: GUI config OR JSON config — export/import for CI/CD

```
┌──────────────────────────────────────────────────┐
│  Masking Rule                    [Visual] [Code]  │
├──────────────────────────────────────────────────┤
│  // Code mode:                                    │
│  {                                                │
│    "column": "users.email",                       │
│    "strategy": "faker_replace",                   │
│    "config": {                                    │
│      "provider": "email",                         │
│      "preserve_domain": false                     │
│    },                                             │
│    "deterministic": true                          │
│  }                                                │
└──────────────────────────────────────────────────┘
```

---

### 21st.dev Component Mapping

Specific 21st.dev components to use (all free, MIT-licensed, copy-paste installation via `npx shadcn@latest add`):

| DataWrangler Feature | 21st.dev Component | Notes |
|---------------------|-------------------|-------|
| **AI Assistant sidebar** | AI Chat components (78 available) | Use "Glowing AI Chat Assistant" or similar; resizable panel |
| **Command palette (Cmd+K)** | `dhileepkumargm/command-palette` | Global search across projects, tables, columns, jobs |
| **Dashboard stat cards** | Cards category + Numbers (animated counters) | 79 card variants, 18 animated number components |
| **Dashboard layout** | "Dashboard with Collapsible Sidebar" | Full layout component, adapt to DataWrangler nav |
| **Form inputs** | Inputs (102), Selects (62), Date Pickers (12) | Progressive disclosure via Accordion for advanced options |
| **Buttons + actions** | Buttons (130) including Progress Button | Use Progress Button for async actions with inline feedback |
| **Notifications** | Notifications (5), Alerts (23), Badges (25) | Bell dropdown with notification list |
| **Empty states** | Empty State component | Customize with DataWrangler illustrations |
| **Loading states** | Spinner/Loaders (21) | Skeleton screens + inline spinners |
| **Modals + drawers** | Dialogs (37), Drawer components | Connection form drawer, rule editor drawer |
| **Sidebars** | Sidebars (10) | Collapsible with icon-only mode |
| **Tabs** | Tabs (38) | Project detail section navigation |
| **Tooltips + help** | Tooltips (28), Popovers (23) | Field-level help text for progressive disclosure |

**Installation**: `npx shadcn@latest add "https://21st.dev/r/[author]/[component]"` copies source into your project (you own it). Also available via Magic MCP in VS Code/Cursor for AI-generated components.

---

## Key Design Patterns

- **DDD Bounded Contexts**: Each domain (connection, discovery, masking, synthetic, subsetting, workflow, compliance) is a self-contained module with entities, value objects, repositories, services, and events
- **CQRS-lite**: Commands (write) and queries (read) separated in the application layer with a mediator for dispatch
- **Repository Pattern**: Domain defines ABCs; infrastructure provides SQLAlchemy implementations
- **Domain Events**: Cross-context communication without direct coupling; events dispatch after transaction commit
- **Connector Abstraction**: All data sources implement `BaseConnector` with `test_connection()`, `get_schemas()`, `get_tables()`, `get_columns()`, `get_sample_data()`, `read_data_chunked()`, `write_data()`
- **Masking Strategy**: Each masking type is a separate strategy class implementing `mask(value, config) -> masked_value`
- **Job System**: All async operations create a `Job` record with checkpoint support and execute via Celery tasks with SSE progress streaming; failed jobs land in DLQ after max retries
- **Circuit Breaker**: External service calls (LLM, data sources) wrapped in pybreaker for fault isolation
- **Storage Abstraction**: Pluggable file storage (local FS, S3, DB BLOBs) behind `StorageBackend` ABC
- **LLM Provider Abstraction**: Pluggable LLM backend (Claude API, Ollama) behind `LLMProvider` ABC with cost tracking
- **FK-Aware Generation**: Topological sort of table dependency graph ensures parent tables generated before children
