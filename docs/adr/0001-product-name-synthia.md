# ADR-0001: Rename Product from "DataWrangler" to "Synthia"

- **Status:** Accepted (decision); rollout Proposed
- **Date:** 2026-05-17
- **Deciders:** Synthia core team
- **Tags:** product, branding, naming

**Implementation status (2026-05-17):** name choice is accepted. The codebase rename (repo, env vars, service names, UI strings, schemas, docs) has not started. The phased rollout described below is itself Proposed and needs scheduling.

## Context

The internal codename "DataWrangler" was chosen early in the project to communicate the breadth of data handling. As the product matured, three concerns emerged:

1. **Tone mismatch with audience.** Ameritas QA/dev teams operate in a regulated insurance domain. "Wrangler" reads informal and manual — the opposite of the product's actual nature (automated, AI-driven, compliance-focused).
2. **Positioning gap.** The differentiator versus Delphix is *synthetic generation* and an LLM-driven assistant. "DataWrangler" says nothing about either.
3. **Persona opportunity.** Because deployment is single-tenant (see ADR-0013) and the product already exposes a chat/LLM surface, the name can carry a friendly persona that lowers QA adoption friction.

The repo, services, env vars, schema, UI strings, and docs all use `datawrangler` / `DataWrangler` today, so a rename has real but manageable cost.

## Decision

Rename the product to **Synthia**.

- **Product display name:** Synthia
- **Code identifier:** `synthia` (lowercase, snake_case where applicable)
- **Persona:** "Your AI test data partner." Voice is helpful, precise, quietly confident — not cute, not corporate.
- **Tagline (working):** *Test data, intelligently made.*

Rollout is phased to avoid a big-bang break (see ADR consequences below).

## Consequences

**Positive**
- Name communicates the product's core promise (synthetic data) in one word.
- Brandable, ownable, pronounceable; no negative connotations.
- Pairs naturally with the LLM-assistant surface ("Ask Synthia for a test dataset").
- Aligns with internal Ameritas tone for regulated/enterprise tools.

**Negative / Tradeoffs**
- Rename touches repo, Docker images, env vars (`DATAWRANGLER_*` → `SYNTHIA_*`), DB schemas, UI strings, docs, marketing surfaces, and dashboards.
- Search/discoverability within Ameritas Confluence/Jira will degrade until links are updated.
- Existing screenshots and recordings in `RELEASE-NOTES-v0.8.md` / `v0.9.md` will reference the old name until those release notes age out.

**Neutral**
- Persona ("she") is optional and not load-bearing; product works without it.
- A `SYNTHIA_*` env var with `DATAWRANGLER_*` fallback gives a one-release compat window.

## Alternatives Considered

- **Verisim** — Strongest single-word fit for *truth-like* synthetic data. Rejected: less brandable, harder to pronounce in meetings, no persona affordance.
- **Aegis / Sentinel / Vault** — Compliance-forward. Rejected: oversells the privacy story and undersells the AI/synthesis differentiator.
- **Mirage** — Evocative. Rejected: connotes *illusion / not real* in a way that can undermine trust ("our test data is a mirage").
- **NorthStar / Cornerstone / Prairie** — Ameritas-tied. Rejected: ties the product too tightly to Ameritas internal identity, limiting future cross-team or partner reuse.
- **Keep "DataWrangler"** — Rejected per Context.

## Related

- Related to: ADR-0013 (single-tenant deployment makes a persona viable)
- References: brainstorm session 2026-05-17; positioning kit in product memory
