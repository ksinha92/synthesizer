# ADR-0005: No Code Dependency on SDV (BUSL License)

- **Status:** Proposed
- **Date:** 2026-05-17
- **Deciders:** Synthia core team, legal review (pending)
- **Tags:** licensing, synthetic-data, compliance

**Implementation status (2026-05-17):** **ADR contradicts current code.** `ctgan>=0.11.0` is declared in `backend/pyproject.toml` and actively imported in `backend/app/infrastructure/engine/statistical_engine.py` (`from ctgan import CTGANSynthesizer`). CTGAN is part of the SDV family. This ADR's "no SDV-family dependencies" stance is aspirational, not current state. Before promoting to Accepted, the team must: (a) confirm the legal posture with Ameritas legal review, (b) decide whether to remove `ctgan` and rebuild the CTGAN path on permissive primitives or to scope this ADR to *new* dependencies only, (c) decide on license-check CI enforcement.

## Context

The [Synthetic Data Vault (SDV)](https://github.com/sdv-dev/SDV) is the most prominent open-source statistical synthetic data library — copulas, CTGAN, TVAE, hierarchical models, FK preservation. It would be the obvious dependency for ADR-0004's Statistical engine.

SDV is published under the **Business Source License 1.1 (BUSL)**. BUSL is a *source-available* license with usage restrictions: it forbids production use that competes with the licensor's commercial offering, and converts to an OSS license only after a change date. While Synthia is an *internal* Ameritas tool, BUSL's "Additional Use Grant" and competitive-use carve-outs introduce legal ambiguity that is not worth the headache for a regulated insurer:

- "Internal use" is not unambiguously safe under BUSL; legal interpretation varies.
- Any future ambition to share Synthia across Ameritas affiliates, partners, or to open-source it would require relicensing or rewriting the dependent code.
- BUSL terms can change at the licensor's discretion before the conversion date.

The team is willing to build the necessary statistical machinery in-house — copulas, conditional sampling, and FK cardinality preservation are well-understood techniques and the SDV *architecture* is documented in papers and READMEs.

## Decision

**Do not take any code dependency on SDV or any other BUSL-licensed library.**

- Synthia's Statistical engine is built in-house using permissively licensed primitives: `copulas` (MIT), `scipy`, `numpy`, `pandas`, and our own conditional-sampling / FK-walk code.
- The SDV project is referenced **only for architectural inspiration**: the shape of the metadata model, the structure of the multi-table sampling pipeline, the published math. Reading the papers is fine; copying source is not.
- Engineers may **not** vendor, fork, or `pip install` SDV (or `ctgan`, `deepecho`, `rdt` — all SDV-family BUSL packages) into the Synthia repo.
- If a BUSL-licensed library appears in a dependency graph, CI must fail. (License-check tooling — `pip-licenses` allowlist — enforces this; see `backend/pyproject.toml`.)

## Consequences

**Positive**
- Zero legal ambiguity about Synthia's right to run, share, or open-source.
- Statistical engine is fully ours: bug fixes, performance tuning, and feature work happen without negotiating BUSL terms.
- Allowlist-based license check catches BUSL drift early in CI.

**Negative / Tradeoffs**
- Initial Statistical engine velocity is slower than `pip install sdv && go`.
- We re-derive some patterns SDV has solved (hierarchical FK walks, mixed-type conditional sampling). We accept this cost.
- Engineers reading SDV docs must internalize the "*inspiration, not code*" rule. Code review explicitly checks for verbatim copying.

**Neutral**
- The `copulas` library (MIT) — separate package, not BUSL — *is* permitted and used.
- This ADR is revisited if SDV relicenses to an OSI-approved license post-change-date.

## Alternatives Considered

- **Use SDV under BUSL with internal-only deployment.** Rejected: legal ambiguity, no future flexibility.
- **Use Gretel / Mostly AI SaaS APIs.** Rejected: sends production-shaped statistical fingerprints off-prem, fails the regulated-data posture in ADR-0009 / ADR-0013.
- **Use YData Synthetic (MIT).** Considered for components; we may borrow specific *generators* (e.g., GAN-style tabular) under their permissive terms in a future ADR. Not a wholesale replacement.

## Related

- Related to: ADR-0004 (three synthetic engines), ADR-0013 (single-tenant deployment)
- References: `backend/pyproject.toml` license allowlist; SDV BUSL text
