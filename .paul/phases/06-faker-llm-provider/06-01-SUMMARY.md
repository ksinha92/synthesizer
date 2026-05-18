---
phase: 06-faker-llm-provider
plan: 01
completed: 2026-03-29
duration: ~25min
---

# Phase 6 Plan 01: Faker Engine + LLM Provider Summary

**Implemented LLM provider abstraction (Claude API + Ollama), Faker synthetic engine with PII-aware generation and FK topological ordering, synthetic bounded context, and generation API endpoints. Also wired PII detector Layer 4 to real LLM provider.**

## Objective

First synthetic data engine (Faker) and the LLM provider that Phase 5's PII Layer 4 needs. Faker handles 80% of generation use cases with PII-type-aware fake data.

## What Was Built

| File | Purpose |
|------|---------|
| `backend/app/infrastructure/ai/llm_provider.py` | LLMProvider ABC (complete/classify/generate_structured), ProviderConfig, create_provider factory, budget enforcement (max_calls_per_batch) |
| `backend/app/infrastructure/ai/claude_provider.py` | ClaudeProvider: Anthropic AsyncAnthropic SDK, lazy key validation, token cost logging, 30s timeout, budget check |
| `backend/app/infrastructure/ai/ollama_provider.py` | OllamaProvider: httpx REST to Ollama API, 60s timeout, JSON format support |
| `backend/app/infrastructure/ai/pii_detector.py` | Updated: Layer 4 now calls real LLM provider via classify(), budget check before call |
| `backend/app/domain/synthetic/value_objects.py` | GenerationMethod, EngineType enums |
| `backend/app/domain/synthetic/entities.py` | SyntheticConfig aggregate root |
| `backend/app/domain/synthetic/repository.py` | SyntheticRepository ABC |
| `backend/app/domain/synthetic/services.py` | BaseSyntheticEngine ABC (generate, preview) |
| `backend/app/domain/synthetic/events.py` | GenerationCompleted domain event |
| `backend/app/infrastructure/engine/faker_engine.py` | FakerEngine: PII→Faker mapping (8 types), data type→Faker (9 types), topological sort with cycle detection + second-pass fix, seed for reproducibility |
| `backend/app/infrastructure/persistence/models/synthetic.py` | SyntheticConfigModel ORM |
| `backend/app/infrastructure/persistence/sqlalchemy/synthetic_repo.py` | SQLAlchemy repository |
| `backend/app/application/synthetic/` | Commands (Create, Generate, Preview), Queries (Get, List), Handlers (preview 10s timeout) |
| `backend/app/api/v1/synthetic.py` | 5 endpoints: POST configs, GET configs, GET config/{id}, POST preview (sync), POST generate (202 async) |
| `backend/app/infrastructure/messaging/synthetic_tasks.py` | Celery task: 2 retries, 30s/60s backoff |
| `backend/alembic/versions/004_synthetic_schema.py` | synthetic_configs table |

## Acceptance Criteria Results

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-1 | LLM provider supports Claude + Ollama | **PASS** | LLMProvider ABC, ClaudeProvider (Anthropic SDK), OllamaProvider (httpx), factory reads LLM_PROVIDER config |
| AC-2 | Faker generates PII-aware data with FK ordering | **PASS** | 8 PIIType→Faker mappings, 9 data type mappings, topological sort, cycle detection with 2nd-pass fix, seed parameter |
| AC-3 | Synthetic API endpoints work | **PASS** | 5 endpoints, preview sync with 10s timeout, generate async 202, auth required |
| AC-4 | PII detector Layer 4 uses real LLM | **PASS** | _detect_llm calls self._llm_provider.classify(), budget check before call, circuit breaker intact |

## Key Patterns/Decisions

1. **Claude key validation on init** (audit #1) — lazy validation on first use. Marks provider as degraded if invalid, doesn't crash app.
2. **Faker seed for reproducibility** (audit #2) — optional seed parameter. Same config + seed = same output. Critical for regression testing.
3. **LLM budget enforcement** (audit #3) — max_calls_per_batch (50 default). Stops calling after limit, logs "llm_budget_exhausted". Prevents runaway cost on large schemas.
4. **Circular FK handling** (audit #4) — Kahn's algorithm detects cycles. Cyclic tables generated with NULL FKs first, then updated in second pass.
5. **Preview timeout** (audit #5) — 10-second asyncio.timeout on synchronous preview. Returns 504 on exceed.
6. **LLM provider as singleton** — reused across requests via DI container. Claude client and Ollama client initialized once.

## Skill Audit

/aegis:audit — not yet installed, deferred per SPECIAL-FLOWS.md.

## Next Phase

Phase 6 complete. Ready for **Phase 7: Additional Connectors (MySQL, MongoDB, Snowflake)**.

---
*Completed: 2026-03-29*
