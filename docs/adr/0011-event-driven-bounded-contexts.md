# ADR-0011: Event-Driven Communication Between Bounded Contexts

- **Status:** Proposed
- **Date:** 2026-05-17
- **Deciders:** Synthia core team
- **Tags:** architecture, ddd, events, coupling

**Implementation status (2026-05-17):** every bounded context has a `domain/<ctx>/events.py` defining dataclass events (`connection`, `discovery`, `masking`, `synthetic`, `subsetting`, `workflow`, `compliance`). However, there is **no in-process event bus, dispatcher, subscriber registry, transactional outbox, or `event_log` table** in the current code. The existing `backend/app/infrastructure/messaging/progress_pubsub.py` is a Redis pub/sub for *job progress* UI streaming, not domain-event cross-context delivery. Promotion to Accepted requires implementing the event bus and `event_log`, then migrating at least one publish/subscribe pair (e.g., `PIIDetected` → masking rule suggestion) as the reference path.

## Context

Synthia's bounded contexts (ADR-0002) frequently need to react to each other's state changes without taking direct dependencies. Examples:

- When discovery finishes classifying a column as PII, the masking context wants to suggest a default masking rule.
- When a workflow step completes, the job tracking context updates progress and the notification context posts to the activity feed.
- When a compliance scan completes, the audit context persists the result for retention.

If discovery directly calls masking (or workflow directly calls notifications), the contexts become coupled in code, deploy, and team ownership. A masking outage stalls discovery; a notifications refactor forces touching workflow internals; ADR-0002's bounded-context discipline erodes within months.

We need an in-process pattern (no broker for now — see ADR-0008) that keeps contexts decoupled while letting them react to each other.

## Decision

**Inter-context communication uses domain events, not direct method calls.**

- **Event definition.** Each context publishes typed events from its `domain/events.py`. Examples: `PIIDetected`, `MaskingRuleSuggested`, `WorkflowStepCompleted`, `ComplianceScanCompleted`. Events are immutable dataclasses with an explicit schema version.
- **Publishing.** Aggregates accumulate uncommitted events. The application layer (command handlers) flushes events to an in-process event bus **after** the database transaction commits (transactional outbox pattern, lightweight variant).
- **Subscribing.** Subscribers register at app startup via the DI container. Subscriber handlers run on the Celery worker pool (ADR-0012), not inside the request thread, so an HTTP request returns as soon as the transaction commits.
- **Schema.** Each event has a `version` field. Adding fields is non-breaking; removing or repurposing requires bumping `version` and keeping a handler for the old version.
- **Audit.** Every event is persisted to an `event_log` table for replay, debugging, and compliance traceability.
- **No cross-context direct imports.** A bounded context's code may import its own domain types and the shared events module. It may not import another context's aggregates, repositories, or handlers.

## Consequences

**Positive**
- Contexts evolve independently. Discovery does not know masking exists; masking subscribes to `PIIDetected` and decides what to do.
- Adding a new reactive feature (e.g., a "scan summary email" context) is purely additive — register a subscriber, no edits to publishers.
- Event log doubles as an audit trail for compliance.
- Failures in one subscriber (e.g., notifications) do not cascade into the publishing context's transaction.

**Negative / Tradeoffs**
- Behavior is distributed across publishers and subscribers; tracing "what happens when discovery completes" requires reading subscribers, not call graphs. Mitigated by an `event_log` UI and per-event subscriber registry inspection.
- Eventual consistency: an HTTP response may return before all subscribers have processed; UI must not assume side effects are visible immediately.
- Schema versioning discipline is required; a careless event-shape change breaks subscribers silently.

**Neutral**
- In-process bus today; a future move to a message broker (Kafka / NATS) is mostly swapping the bus implementation, not the contracts. Re-evaluated when a context is extracted as a separate service.

## Alternatives Considered

- **Direct cross-context calls.** Rejected: defeats ADR-0002's bounded-context boundaries within months.
- **Shared "core" module that publishers and subscribers both depend on.** Rejected: shared module becomes a dumping ground; transitive coupling reappears.
- **External broker (Kafka / RabbitMQ) from day one.** Rejected: ops cost (ADR-0008's single-VM Compose target). In-process bus + Celery is sufficient for current scale.

## Related

- Related to: ADR-0002 (DDD), ADR-0012 (Celery), ADR-0008 (deployment), ADR-0009 (PIIDetected event consumer)
- References: `backend/app/domain/*/events.py`, `backend/app/application/event_bus.py` (planned)
