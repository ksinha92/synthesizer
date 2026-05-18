# ADR-0009: Four-Layer PII Detection Pipeline

- **Status:** Proposed
- **Date:** 2026-05-17
- **Deciders:** Synthia core team, security architect, compliance lead (review pending)
- **Tags:** pii, compliance, ai, security

**Implementation status (2026-05-17):** `presidio-analyzer>=2.2.0` and `spacy>=3.7.0` are declared in `backend/pyproject.toml`, and `backend/app/domain/discovery/services.py` exposes a `SchemaDiscoveryService.discover(...)`. The exact four-layer pipeline, weighted aggregation, and auto/review/reject thresholds described here have **not been verified end-to-end** against the current discovery service — they reflect the design in DATAWRANGLER.md. Promotion to Accepted requires (a) code audit of the discovery pipeline against this ADR, (b) a labeled eval set with the proposed weights, (c) compliance-lead sign-off on the thresholds.

## Context

Accurate PII detection is the load-bearing capability for everything downstream: masking rule suggestions, compliance reports, audit trails, and the safety of any data leaving the Ameritas perimeter (ADR-0006). Any *single* detection technique has known failure modes:

- **Regex** is precise on well-formatted patterns (SSN, credit card, phone, email) but misses everything unstructured.
- **NER models (spaCy, Presidio)** catch unstructured PERSON / LOCATION / DATE_TIME but produce false positives on enterprise data ("Jersey" tagged as a location, product names tagged as people).
- **Column-name heuristics** are high-leverage when columns are named clearly (`ssn`, `first_name`) and useless when they're not (`field_3`, `c_data`).
- **LLM classification** is the most flexible but the slowest, costliest, and (for external providers) has data-residency implications.

Compliance regimes Synthia serves (GDPR / HIPAA / CCPA) all require defensible classification: a single technique's false-negative rate is a regulatory exposure, and an LLM-only approach is too expensive to run on every column on every schema sync.

## Decision

Use a **four-layer detection pipeline** with weighted confidence aggregation. Layers run cheapest-first; later layers run only when earlier-layer confidence is insufficient.

- **Layer 1 — Regex.** High-precision patterns: SSN, credit card, phone, email, IP, ZIP, EIN. Fast, deterministic, zero data leaves the box.
- **Layer 2 — Presidio + spaCy NER.** Entity recognition for PERSON, LOCATION, DATE_TIME, IBAN, etc. Runs in-process.
- **Layer 3 — Column-Name Heuristics.** Matches column names against a maintained pattern dictionary (`ssn|social|tax_id`, `dob|birth|date_of_birth`, etc.) with token weighting.
- **Layer 4 — LLM Classification.** Invoked **only** when combined confidence from Layers 1–3 is below `0.4`. Sends a redacted column sample + name + type to the configured `LLMProvider` (default Ollama per ADR-0006).

**Aggregation:**

- Each layer emits a confidence score in `[0, 1]` and an evidence list.
- Per-column confidence is a weighted combination (weights are configurable; defaults derived from internal eval).
- **`>= 0.65`** → auto-classify, masking rule suggested.
- **`0.4 – 0.65`** → needs-review queue (human-in-the-loop UI).
- **`< 0.4` after all four layers** → not PII (but still surfaced for explicit override).

**Auditability:** every detection persists which layers fired, raw scores, evidence snippets, the final aggregated confidence, and (if Layer 4 ran) the provider used and the redacted prompt hash.

## Consequences

**Positive**
- Cheapest layers handle the common case; LLM cost is bounded by Layer 4's gating threshold.
- Defensible classification: each detection has an explainable audit trail of which signals fired.
- Data-residency-friendly: Layer 4 defaults to in-perimeter Ollama; column samples are redacted before any provider call.
- Human-in-the-loop band (`0.4–0.65`) captures uncertainty as a UI affordance rather than a silent miss.

**Negative / Tradeoffs**
- Four layers means four maintenance surfaces (regex dictionaries, NER model versions, heuristic patterns, prompts).
- Weights are tuned empirically; first-deploy accuracy needs a labeled eval set per data class.
- Layer 4 prompt regressions can shift confidence distributions; prompt changes are versioned and gated.

**Neutral**
- Latency: Layers 1–3 are sub-second per column; Layer 4 adds 1–5s when invoked.
- Configurable thresholds let compliance leads tune precision/recall by data class.

## Alternatives Considered

- **Presidio-only.** Rejected: false-positive rate on enterprise data; misses structured patterns Presidio doesn't ship for.
- **LLM-only.** Rejected: cost, latency, residency, and reproducibility.
- **Vendor PII service (e.g., Macie, BigID).** Rejected: data egress + cost; misaligned with on-prem deployment (ADR-0008).

## Related

- Related to: ADR-0006 (LLM provider — Layer 4), ADR-0011 (`PIIDetected` event consumed by masking), ADR-0013 (single-tenant residency)
- References: DATAWRANGLER.md "Intelligent PII Detection (4-Layer Pipeline)"; `backend/app/domain/discovery/`
