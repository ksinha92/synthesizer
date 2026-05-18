# ADR-0002: Domain-Driven Design with Bounded Contexts

- **Status:** Accepted
- **Date:** 2026-05-17
- **Deciders:** Synthia core team
- **Tags:** architecture, backend, ddd

**Implementation status (2026-05-17):** verified. `backend/app/` contains `domain/`, `application/`, `infrastructure/`, `api/` directories with the listed bounded contexts (`connection`, `discovery`, `masking`, `synthetic`, `subsetting`, `workflow`, `compliance`) plus `shared/`. Each context has `entities.py`, `value_objects.py`, `repository.py`, `events.py`, and `services.py` files consistent with the structure described here.

## Context

Synthia spans connection management, schema discovery, PII detection, masking, synthetic generation, subsetting, workflow orchestration, and compliance reporting. Modeling all of this as a single layered application (controllers → services → models) would couple unrelated concerns: a discovery change would force masking redeploys, masking rule edits would touch synthetic generation code, and the domain would become unintelligible as teams grow.

The team is 4+ developers building over a 26-week timeline (per PLANNING.md), and the platform must remain extensible to new connectors, engines, and compliance regimes. The product is also AI-heavy — confidence scores, model abstractions, and asynchronous jobs need clear boundaries to remain testable.

## Decision

Adopt **Domain-Driven Design** with explicit **bounded contexts** as the backend's primary structuring principle.

- **Contexts (current):** `connection`, `discovery`, `masking`, `synthetic`, `subsetting`, `workflow`, `compliance`.
- **Per-context structure:** `domain/` (entities, value objects, repositories as ABCs, domain services, domain events), `application/` (use cases / command + query handlers), `infrastructure/` (SQLAlchemy / Celery / connector adapters), `api/` (FastAPI routers).
- **Domain layer purity:** zero framework dependencies — no SQLAlchemy, no FastAPI, no Celery imports in `domain/`. This is enforced by code review and (where practical) static checks.
- **Wiring:** a DI container (`dependency-injector`) wires infrastructure implementations to domain ABCs at app startup.
- **Cross-context communication:** via domain events, never direct calls (see ADR-0011).

The current backend layout (`backend/app/{domain,application,infrastructure,api}`) reflects this decision.

## Consequences

**Positive**
- New connectors / engines / compliance regimes plug in via narrow ABCs without touching unrelated contexts.
- Domain logic is testable without a database, queue, or HTTP layer.
- Bounded contexts give the team natural ownership boundaries.
- Aligns with the event-driven approach in ADR-0011 and the fault-tolerance posture (idempotent commands, transactional event dispatch).

**Negative / Tradeoffs**
- More upfront structure than a flat MVC app; new contributors need a short ramp on DDD vocabulary.
- ABC + DI wiring adds boilerplate for simple CRUD-style features.
- Risk of *anemic* domain models if teams default to putting logic in handlers; reviewers must guard against this.

**Neutral**
- Bounded contexts share a single PostgreSQL instance for now (separate schemas per context). Splitting databases is deferred until a context's load justifies it.

## Alternatives Considered

- **Layered MVC (controllers → services → models).** Rejected: doesn't scale to the number of distinct domains Synthia covers; cross-cutting changes become invasive.
- **Microservices from day one.** Rejected: ops overhead unjustified for a single-tenant internal deployment (ADR-0013) and a small team. Bounded contexts give us the option to extract services later without rewriting the model.
- **Hexagonal-only (without DDD vocabulary).** Rejected: hexagonal addresses I/O isolation but doesn't give us the *modeling* discipline (aggregates, value objects, ubiquitous language) that the domain complexity calls for.

## Related

- Related to: ADR-0011 (event-driven communication), ADR-0012 (Celery + Redis), ADR-0013 (single-tenant)
- References: `backend/app/` structure; DATAWRANGLER.md "Architectural Principles" section
