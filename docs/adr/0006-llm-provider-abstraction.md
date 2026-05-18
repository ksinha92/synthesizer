# ADR-0006: LLM Provider Abstraction (Claude + Ollama)

- **Status:** Accepted (provider abstraction + both adapters); routing rules and outbound PII redaction Proposed
- **Date:** 2026-05-17
- **Deciders:** Synthia core team, security architect (routing/redaction review pending)
- **Tags:** llm, architecture, security, cost

**Implementation status (2026-05-17):** `backend/app/infrastructure/ai/` contains `llm_provider.py` (interface), `claude_provider.py`, `ollama_provider.py`, and `llm_settings.py`. `pybreaker>=1.2.0` is declared in `pyproject.toml`. The **per-workload routing rules** (PII Layer 4 → Ollama; assistant → Claude; synthetic with fallback) and the **outbound PII redaction pass before external calls** described here have not been verified end-to-end in code and should be treated as the design target, not current behavior. The provider-selection routing layer and the redaction guard need a confirming implementation pass before this ADR is fully Accepted.

## Context

Synthia uses LLMs for three distinct workloads:

1. **PII classification** — Layer 4 fallback in the detection pipeline (ADR-0009), called when regex/NER/heuristics confidence is low.
2. **Synthetic generation** — the LLM engine in ADR-0004; freeform fields and natural-language-prompted generation.
3. **User-facing assistant** — the "Ask Synthia" chat surface that interprets natural language data generation requests.

These workloads have conflicting needs:

- **Quality:** assistant and synthetic generation benefit from a frontier model (Claude).
- **Cost:** PII Layer 4 fires often and on potentially sensitive column samples; per-call inference cost matters.
- **Data residency:** column samples passed to Layer 4 may contain PII. Some Ameritas data classifications cannot leave Ameritas infrastructure regardless of vendor BAA status.
- **Availability resilience:** an external API outage should not stop discovery jobs.

Hard-coding any single provider would force a tradeoff that doesn't survive contact with these workloads.

## Decision

Introduce an `LLMProvider` abstraction with **two MVP implementations** and a routing layer that selects per-call.

- **Interface:** `LLMProvider` exposes `complete(prompt, system, schema=None, max_tokens, temperature) -> LLMResponse`. Streaming variant `stream_complete(...)` for the assistant.
- **Implementations (MVP):**
  - `ClaudeProvider` — Anthropic SDK, used by default for the assistant and the synthetic LLM engine.
  - `OllamaProvider` — self-hosted (configurable model: `llama3.1`, `mistral`, etc.), default for PII Layer 4 and any call whose payload is flagged "do not exfiltrate."
- **Routing rules** (defined in config, not code):
  - PII Layer 4 → Ollama by default. Switchable per data classification.
  - Synthetic LLM engine → Claude by default. Falls back to Ollama on Claude outage or rate limit.
  - Assistant → Claude. No Ollama fallback (UX prefers honest "Synthia is unavailable" over degraded answers).
- **PII guard:** every prompt passes through an outbound redaction pass; column samples sent to external providers have detected PII tokens replaced with placeholder values.
- **Circuit breaker:** `pybreaker` around each provider; open after 5 failures, half-open after 60s.

## Consequences

**Positive**
- Each workload picks its own quality/cost/residency point.
- Internal-only Ollama path keeps high-classification PII inside Ameritas perimeter.
- Adding a third provider (e.g., Azure OpenAI for a future BAA-friendlier path) is a new class + config entries.
- Circuit breaker + provider fallback prevents an outage from stalling discovery jobs.

**Negative / Tradeoffs**
- Two providers means two sets of credentials, two failure modes, two cost dashboards.
- Ollama latency and quality lag Claude. PII Layer 4 accuracy must be evaluated on the actual model deployed.
- Provider-specific features (Claude tool-use, response_format) are exposed only through the lowest-common-denominator interface unless explicitly extended.

**Neutral**
- Provider choice is observable in audit logs (compliance requirement).
- Tests can stub `LLMProvider` for deterministic CI runs.

## Alternatives Considered

- **Claude-only.** Rejected: data residency posture and outage risk.
- **Ollama-only.** Rejected: assistant UX and synthetic LLM engine quality.
- **LangChain provider abstraction.** Rejected: heavy dependency surface, frequent breaking changes, and we use a narrow subset of its capabilities. A 100-line ABC plus two adapters is the lower-cost path.

## Related

- Related to: ADR-0004 (LLM synthetic engine), ADR-0009 (Layer 4 of PII detection), ADR-0013 (single-tenant residency)
- References: `backend/app/infrastructure/llm/` (planned); DATAWRANGLER.md "Tech Stack — LLM Providers"
