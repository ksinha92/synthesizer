# ADR-0012: Celery + Redis for Async Task Processing

- **Status:** Accepted (broker + worker layout); per-queue scaling, DLQ, and circuit-breaker policies Proposed
- **Date:** 2026-05-17
- **Deciders:** Synthia core team
- **Tags:** infrastructure, async, jobs, fault-tolerance

**Implementation status (2026-05-17):** `backend/app/infrastructure/messaging/celery_app.py` and per-context task modules (`masking_tasks.py`, `synthetic_tasks.py`, `workflow_tasks.py`) are present; `pybreaker>=1.2.0` is declared in `pyproject.toml`. The **per-queue segmentation** (`discovery`, `masking`, `synthetic`, `llm`, `default`), the **DLQ surface in the admin UI**, and the specific **retry policies per task class** described here have not been individually verified against the current queue configuration. Treat those specifics as the design target, not current state.

## Context

Synthia's value-producing operations are long-running and chunkable:

- Schema discovery across many tables / collections.
- Masking large tables in parallel chunks.
- Synthetic generation jobs that emit GB-scale output.
- LLM calls (rate-limited; need retry-with-jitter).

These must run out-of-band of HTTP requests, support retries with exponential backoff, surface progress to the UI, and be replayable for compliance. They also feed downstream domain-event subscribers (ADR-0011).

Constraints:

- Deployment is Docker Compose on VMs (ADR-0008) — no Kubernetes-native job system available.
- The team is Python-centric.
- Operators need a familiar dashboard, not a custom UI.

## Decision

**Use Celery as the async task framework with Redis as both broker and result backend.**

- **Broker:** Redis (single instance in MVP; Redis Cluster path documented for scale).
- **Result backend:** Redis for short-lived results; long-lived job state lives in PostgreSQL (`jobs` table with progress, status, chunk-level checkpoints).
- **Worker topology:** dedicated queues per workload class — `discovery`, `masking`, `synthetic`, `llm`, `default`. Each can be scaled independently (`docker compose up --scale masking_worker=N`).
- **Retry policy** (per task type):
  - Discovery: 3 retries, 30s/60s/120s backoff.
  - Masking: 2 retries (operations are idempotent via chunk tracking).
  - LLM: 5 retries with jitter (handles API rate limits).
- **Dead-letter queue:** after max retries, tasks land in a `dlq` queue surfaced in the admin UI for manual review.
- **Circuit breakers:** `pybreaker` around external calls (LLM providers, customer database connections). Open after 5 failures, half-open after 60s.
- **Idempotency:** every job has a stable `job_id`; chunk processors record completion before advancing, so a re-run resumes rather than restarts.
- **Domain-event dispatch:** event-bus subscribers run on Celery (ADR-0011), inheriting all retry / DLQ semantics.
- **Observability:** Flower for live worker / task visibility; Prometheus metrics for queue depth, task duration, failure rate.

## Consequences

**Positive**
- Mature, well-documented framework with a large operator community.
- Per-queue scaling matches Synthia's mixed workload — LLM workers don't starve fast masking jobs.
- Retry / DLQ / circuit-breaker patterns are encoded once and reused by every long-running operation.
- Flower + Prometheus give immediate operator insight.

**Negative / Tradeoffs**
- Celery's configuration surface is large; misconfiguration (prefetch, ack semantics, soft vs. hard timeouts) is the most common operational footgun. Mitigated by a vetted base configuration and a runbook.
- Redis as broker has limits: at-most-once semantics are tricky; we rely on idempotency rather than exactly-once guarantees.
- Adding a new task type means choosing a queue, declaring retry policy, and adding monitoring — a small but real per-feature tax.

**Neutral**
- Redis is also used as a low-volume cache for hot read paths; cache and broker keys are namespaced to avoid collision.
- Switching brokers (e.g., to RabbitMQ) is feasible but unnecessary at current scale.

## Alternatives Considered

- **RQ (Redis Queue).** Considered. Rejected: simpler than Celery but lacks the retry / circuit-breaker / queue-segmentation maturity we need.
- **Dramatiq.** Considered. Rejected: smaller community, fewer operator references inside Ameritas.
- **arq (asyncio-native).** Considered. Rejected: async-only worker model fights blocking pandas/SQLAlchemy paths in masking and synthetic.
- **AWS Step Functions / SQS.** Rejected: violates ADR-0008's "on-prem VMs" posture and adds cloud egress for high-volume jobs.

## Related

- Related to: ADR-0002 (DDD), ADR-0008 (deployment), ADR-0011 (event bus runs on Celery), ADR-0006 (LLM retry semantics)
- References: `backend/app/infrastructure/celery/`, `docker-compose.dev.yml` worker services
