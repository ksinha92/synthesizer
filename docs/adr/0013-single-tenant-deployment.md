# ADR-0013: Single-Tenant Internal Deployment

- **Status:** Accepted
- **Date:** 2026-05-17
- **Deciders:** Synthia core team, product, security architect
- **Tags:** deployment, product, security

**Implementation status (2026-05-17):** consistent with DATAWRANGLER.md's "Target: Internal Ameritas tool (single-tenant)" charter and with the absence of tenant-scoping in observed schemas. A targeted audit for any latent `tenant_id` fields, multi-org assumptions, or per-tenant feature flags has not been performed and should be done before this ADR's "single trust boundary" is treated as a load-bearing security claim.

## Context

Synthia could be designed for any of three operating models:

1. **Multi-tenant SaaS** — Synthia operates a single platform; many customers share infrastructure with logical isolation. Implies tenant-scoped data models, row-level security, per-tenant billing, isolation testing, and a hardened public attack surface.
2. **Multi-instance, customer-deployed** — Each customer runs their own Synthia on their own infra. No tenant isolation in code; product is shipped, not operated.
3. **Single-tenant, internal-only (Ameritas)** — Synthia is one platform serving one customer (Ameritas), deployed by Ameritas onto Ameritas infrastructure.

Choosing the model is foundational; nearly every other decision (auth, storage, deployment, residency, LLM routing, UI personalization) inherits assumptions from it. The product's current charter is to replace Delphix *inside Ameritas* and serve Ameritas QA/dev teams.

## Decision

**Synthia is single-tenant and internal-only.**

- One deployment exists: the Ameritas production instance, with dev and staging environments mirroring it.
- All data models assume a single trust boundary. There is no `tenant_id` column; users, jobs, and connections belong to one organization.
- Auth (ADR-0007) integrates with the Ameritas corporate IdP — no customer-specific IdP federation paths.
- Storage (ADR-0010), LLM routing (ADR-0006), and deployment (ADR-0008) all assume Ameritas-managed infrastructure with Ameritas's data-residency posture.
- The product is internal-facing; UI tone, persona (Synthia, per ADR-0001), and copy may reflect Ameritas context.

**Reversibility note:** if Ameritas later wants to share Synthia with affiliates or partners, the path is **multi-instance** (each affiliate runs their own deployment), not retrofitting multi-tenancy. Multi-tenant is intentionally a one-way door we have *not* walked through.

## Consequences

**Positive**
- Vastly smaller security surface: no tenant isolation bugs possible because there is no tenancy concept.
- Simpler data models, simpler queries, simpler tests — every join is implicitly tenant-scoped because there's only one tenant.
- Product can be personalized to Ameritas's vocabulary, compliance regime, and workflows without "make it generic" pressure.
- Persona (Synthia, ADR-0001) carries weight because the UI doesn't need to feel neutral for unknown customers.

**Negative / Tradeoffs**
- Cannot become a shared multi-customer SaaS without a substantial rewrite of the data model, auth, and isolation layer.
- Some patterns (per-tenant config, tenant-scoped feature flags) are unavailable.
- Cross-Ameritas-affiliate use requires standing up additional deployments rather than logical separation.

**Neutral**
- Single-tenancy does not mean single-environment: dev, staging, and prod are separate deployments.
- Internal-only does not mean "no external dependencies" — Claude API and similar external services are still used, with the residency guardrails in ADR-0006.

## Alternatives Considered

- **Multi-tenant SaaS.** Rejected: explicit non-goal; vastly expands scope, security surface, and ops cost for a use case that doesn't exist.
- **Multi-instance, customer-deployed.** Rejected for now: would require packaging the product for unknown environments, which slows internal velocity. Still the future-flexibility option if Ameritas chooses to share.
- **Hybrid (single-tenant now, multi-tenant later as a flag).** Rejected: half-built multi-tenancy is worse than no multi-tenancy — every developer pays the tax of carrying a `tenant_id` they never use.

## Related

- Related to: ADR-0001 (Synthia naming benefits from internal-only context), ADR-0006 (LLM residency), ADR-0007 (Ameritas IdP), ADR-0008 (Ameritas VMs), ADR-0010 (Ameritas object store)
- References: DATAWRANGLER.md "Target: Internal Ameritas tool (single-tenant)"
