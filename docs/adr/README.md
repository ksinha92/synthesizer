# Architecture Decision Records (ADRs)

This directory captures significant architectural and product decisions made for **Synthia** (formerly "DataWrangler"), Ameritas's internal AI-powered Test Data Management platform.

## What is an ADR?

An ADR records a decision that has meaningful, long-lived consequences — something a future engineer would want to know the *why* behind, not just the *what*. ADRs are immutable once accepted: if a decision changes, write a new ADR that supersedes the old one. We follow the [MADR](https://adr.github.io/madr/) lightweight format.

## When to write one

Write an ADR when the decision:

- Affects multiple bounded contexts or services
- Constrains future implementation choices (frameworks, protocols, vendors)
- Encodes a tradeoff that isn't obvious from reading the code
- Carries legal, licensing, security, or compliance implications
- Names or rebrands a product, module, or external interface

Do **not** write an ADR for routine implementation choices (naming a variable, picking a list vs. dict, choosing one of two equivalent libraries).

## Status semantics

| Status        | Meaning                                                                                              |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| `Proposed`    | Written but not ratified. Direction is captured for review; not yet binding on implementation.       |
| `Accepted`    | Decision is ratified by the listed deciders **and** verified to match (or guide) current code.       |
| `Deprecated`  | No longer in force; not yet replaced.                                                                |
| `Superseded by ADR-XXXX` | Replaced by a newer ADR.                                                                |

**Rule:** Do not mark an ADR `Accepted` unless either (a) the listed deciders have ratified it, or (b) the codebase already implements it and this ADR is documenting the realized decision. Each Accepted ADR carries an `Implementation status` note tying its claims to current code or explicitly flagging gaps.

## Format

Use [`template.md`](./template.md). Filename pattern: `NNNN-kebab-case-title.md`. Numbers are sequential and never reused.

## Index

| #    | Title                                                             | Status                                         | Date       |
| ---- | ----------------------------------------------------------------- | ---------------------------------------------- | ---------- |
| 0001 | [Rename to Synthia](./0001-product-name-synthia.md)               | Accepted (decision); rollout Proposed          | 2026-05-17 |
| 0002 | [Domain-Driven Design with Bounded Contexts](./0002-domain-driven-design.md) | Accepted                            | 2026-05-17 |
| 0003 | [Hybrid Frontend Design System](./0003-hybrid-frontend-design-system.md) | Accepted                                | 2026-05-17 |
| 0004 | [Three Synthetic Data Engines](./0004-three-synthetic-data-engines.md) | Accepted (caveat: see ADR-0005)             | 2026-05-17 |
| 0005 | [No SDV Code Dependency (BUSL License)](./0005-no-sdv-code-dependency.md) | **Proposed** — contradicts current `ctgan` dep | 2026-05-17 |
| 0006 | [LLM Provider Abstraction](./0006-llm-provider-abstraction.md)    | Accepted (abstraction); routing/redaction Proposed | 2026-05-17 |
| 0007 | [SSO via SAML/OIDC with JWT Fallback](./0007-sso-saml-oidc-auth.md) | **Proposed** (OIDC partial; SAML not in deps) | 2026-05-17 |
| 0008 | [Docker Compose on VMs (not Kubernetes)](./0008-docker-compose-on-vms.md) | Accepted                                | 2026-05-17 |
| 0009 | [Four-Layer PII Detection Pipeline](./0009-four-layer-pii-detection.md) | **Proposed** — pipeline not verified end-to-end | 2026-05-17 |
| 0010 | [Pluggable Storage Backend](./0010-pluggable-storage-backend.md)  | Accepted (minimal ABC + Local + S3 + DI-resolved); streaming, `exists`, `presign`, per-domain routing, DB BLOB — all **Proposed** | 2026-05-17 |
| 0011 | [Event-Driven Communication Between Bounded Contexts](./0011-event-driven-bounded-contexts.md) | **Proposed** — events defined; bus not implemented | 2026-05-17 |
| 0012 | [Celery + Redis for Async Task Processing](./0012-celery-redis-task-queue.md) | Accepted (broker); policies Proposed | 2026-05-17 |
| 0013 | [Single-Tenant Internal Deployment](./0013-single-tenant-deployment.md) | Accepted                                  | 2026-05-17 |

## Promotion checklist (Proposed → Accepted)

When promoting a Proposed ADR:

1. Confirm the listed deciders have actually reviewed and ratified it (not just the author).
2. Verify the ADR's claims against current code; resolve any contradiction either by code change or by editing the ADR.
3. Update the `Status` line and the `Implementation status` note.
4. Update this index.
5. Commit with message `adr(NNNN): promote to Accepted — <one-line reason>`.
