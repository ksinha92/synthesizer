# Enterprise Plan Audit Report

**Plan:** .paul/phases/06-faker-llm-provider/06-01-PLAN.md
**Audited:** 2026-03-29
**Verdict:** Conditionally Acceptable (after applied fixes)

---

## 1. Executive Verdict

**Conditionally acceptable.** The LLM provider abstraction and Faker engine are well-architected. However, the original plan had no API key validation (silent degradation risk), no Faker seed for reproducibility, no LLM cost budget enforcement, no circular FK handling in topological sort, and no timeout on the synchronous preview endpoint. All remediated.

---

## 2. What Is Solid

- **LLMProvider ABC** with complete/classify/generate_structured is the right interface. Factory pattern from config is clean.
- **Dual provider support** (Claude + Ollama) gives cost flexibility. Config-driven selection enables per-environment tuning.
- **PII-type → Faker provider mapping** is comprehensive (8 PII types mapped, 9 data types mapped). This produces realistic test data that matches the schema's actual content patterns.
- **Topological sort for FK ordering** ensures referential integrity in generated data.
- **Synthetic bounded context** follows established DDD patterns (entities, repository, services, events).
- **Celery task for async generation** with retry is the correct pattern.

---

## 3. Enterprise Gaps Identified

1. **No API key validation on init** — invalid key silently fails on every Layer 4 call, opening circuit breaker. Provider should validate on creation.
2. **Non-deterministic Faker output** — same config produces different data each run. Reproducibility needed for regression testing and audit.
3. **No LLM cost budget** — 10,000-column discovery could trigger thousands of LLM calls. No limit beyond circuit breaker (which only trips on failures, not volume).
4. **Circular FK not handled** — self-referential FKs (manager_id → users.id) cause infinite loop in topological sort.
5. **Preview endpoint has no timeout** — synchronous Faker generation against complex schemas could hang.

---

## 4. Upgrades Applied to Plan

### Must-Have (Release-Blocking)

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| 1 | No API key validation | Task 1, ClaudeProvider | Validate key on __init__ via lightweight API check. Mark degraded if invalid, don't crash. |
| 2 | Non-deterministic Faker | Task 2, FakerEngine | Accept optional seed parameter. Faker(seed=seed) for reproducible output. |

### Strongly Recommended

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| 3 | No LLM cost budget | Task 1, ClaudeProvider | max_calls_per_batch (default 50). Stop calling after limit, log "llm_budget_exhausted". |
| 4 | Circular FK in topo sort | Task 2, _build_generation_order | Detect cycles, break by generating with NULL FKs first, update in second pass. |
| 5 | Preview no timeout | Task 3, PreviewHandler | 10-second asyncio.timeout, return 504 on exceed. |

### Deferred (Can Safely Defer)

| # | Finding | Rationale for Deferral |
|---|---------|----------------------|
| 6 | Write-to-target-DB | Already scoped out. Phase 9. |

---

## 5. Audit & Compliance Readiness

**Reproducibility:** Seeded Faker (finding #2) enables audit-grade reproducibility — same config + seed = same output. Important for regression testing and compliance evidence.

**Cost control:** LLM budget enforcement (finding #3) prevents runaway API costs during large-scale discovery. Combined with circuit breaker, provides dual protection.

**Resilience:** API key validation on init (finding #1) surfaces configuration problems at startup, not during production PII detection runs.

---

## 6. Final Release Bar

**What must be true:**
- ClaudeProvider validates API key on initialization
- FakerEngine accepts seed for deterministic output
- LLM calls capped at max_calls_per_batch (50 default)
- Topological sort handles circular FKs
- Preview endpoint has 10-second timeout

**Sign-off:** After 5 applied fixes, this plan delivers a solid foundation for synthetic data generation with proper cost controls and reproducibility.

---

**Summary:** Applied 2 must-have + 3 strongly-recommended upgrades. Deferred 1 item.
**Plan status:** Updated and ready for APPLY

---
*Audit performed by PAUL Enterprise Audit Workflow*
*Audit template version: 1.0*
