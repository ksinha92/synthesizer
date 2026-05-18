# ADR-0004: Three Synthetic Data Engines from Day One

- **Status:** Accepted
- **Date:** 2026-05-17
- **Deciders:** Synthia core team
- **Tags:** synthetic-data, architecture, mvp

**Implementation status (2026-05-17):** verified. `backend/app/infrastructure/engine/` contains `faker_engine.py`, `statistical_engine.py`, and `llm_engine.py`. Caveat: the Statistical engine currently uses `ctgan` (see ADR-0005, which is Proposed and contradicts the "no SDV-family" stance until resolved). The common `SyntheticEngine` ABC interface and per-column mixed-engine job specs should be confirmed against current code before extension.

## Context

Synthetic data needs vary by use case:

- **Volume + speed** — load tests, smoke runs, dev fixtures. Caller wants thousands of rows per second; statistical realism is irrelevant.
- **Statistical fidelity** — performance testing, analytics validation, demos that must "look like prod" at the distribution level (joint distributions, correlations, foreign key cardinality).
- **Semantic realism** — UAT scenarios, customer-facing demos, edge-case generation where rows must read like plausible human data (a believable claim narrative, a coherent address + name + DOB combination).

Delphix offers only reference-file substitution. Caller demand at Ameritas spans all three of the categories above, and which engine wins depends on the QA scenario, not on a global setting. Building one engine first and adding others later would force every existing job spec to migrate when the next engine ships.

## Decision

Ship **three synthetic engines from MVP**, all implementing a common `SyntheticEngine` ABC and selectable per-job (and, where useful, per-column):

1. **Faker** — fast, deterministic, locale-aware. Default for volume use cases.
2. **Statistical** — distribution-preserving multivariate generation, built **in-house** drawing architectural inspiration from SDV (copulas, conditional sampling, FK cardinality preservation). See ADR-0005 for why we do not depend on SDV directly.
3. **LLM** — Claude API and self-hosted Ollama via the provider abstraction in ADR-0006. Used for free-text fields, semantic edge cases, and natural-language-prompted generation.

A job spec may mix engines — e.g., Statistical for numeric columns, Faker for IDs, LLM for `claim_notes`.

## Consequences

**Positive**
- Covers all three user demand categories from day one; no painful migration when a second/third engine arrives.
- Per-column engine selection produces realistic mixed-mode datasets impossible with a single engine.
- Common ABC enforces a consistent contract (`fit`, `sample`, `seed`, `metadata`) and a single job-spec format.

**Negative / Tradeoffs**
- Three engines means three sets of tests, three dependency surfaces, and three failure modes.
- The Statistical engine is the largest single workstream (multivariate models, FK preservation). It is also the highest-leverage differentiator vs. Delphix.
- LLM generation is the slowest and most expensive per row; users need clear guidance on when to use it.

**Neutral**
- Engines do not share state; each is invoked per chunk by the Celery pipeline (ADR-0012).
- Statistical engine is licensed permissively (in-house code), unlike SDV (BUSL — see ADR-0005).

## Alternatives Considered

- **Ship only Faker for MVP, add others later.** Rejected: Faker alone is indistinguishable from Delphix on the dimensions that matter (no statistical fidelity, no semantic realism), erasing the product's differentiation at MVP.
- **Use SDV directly for the Statistical engine.** Rejected — see ADR-0005 (BUSL license incompatible with internal-tool distribution semantics).
- **LLM-only.** Rejected: cost, latency, and determinism rule it out for high-volume cases; reproducibility for compliance audits is harder.

## Related

- Supersedes: none
- Related to: ADR-0005 (no SDV dependency), ADR-0006 (LLM provider abstraction), ADR-0012 (Celery), ADR-0009 (PII detection feeds engine choice)
- References: DATAWRANGLER.md "Synthetic Data" sections; PLANNING.md Phase 1
