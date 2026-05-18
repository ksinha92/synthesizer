# ADR-0008: Docker Compose on VMs (Not Kubernetes)

- **Status:** Accepted
- **Date:** 2026-05-17
- **Deciders:** Synthia core team, platform engineering
- **Tags:** deployment, operations, infrastructure

**Implementation status (2026-05-17):** verified at the file level. `docker-compose.dev.yml` and `docker-compose.prod.yml` are present at repo root; `docs/DEPLOYMENT.md` exists. Nginx hardening, Prometheus metrics, and health-check coverage are referenced in recent release notes (v0.9). Exact service topology, scaling defaults, and backup automation should be audited against current Compose files before promoting the runbook.

## Context

Synthia is an internal, single-tenant Ameritas platform (ADR-0013) running on Ameritas-managed infrastructure. The platform comprises ~6 long-running services (FastAPI app, Postgres, Redis, Celery workers, Flower, Next.js frontend, optional Ollama) plus periodic jobs.

Choosing the orchestrator is a one-way door: it constrains ops staffing, monitoring stack, deployment automation, and developer onboarding for years.

Candidate orchestrators:

- **Kubernetes (EKS / AKS / on-prem).** Industry default for orchestration. Expensive in operator skill, control-plane cost, and the supporting ecosystem (ingress controllers, secrets operators, monitoring, GitOps).
- **Docker Compose on VMs.** Simple, well-understood. No control plane. Limited autoscaling and self-healing.
- **Nomad.** Middle ground. Less common in the Ameritas environment, fewer in-house operators.

Ameritas platform engineering already operates VMs at scale. Kubernetes is *available* but is not the path of least operator overhead for a single-tenant internal service whose traffic profile is bursty-batch, not steady-state.

## Decision

**Deploy Synthia on Docker Compose, running on Ameritas-managed VMs.**

- One Compose file per environment (`docker-compose.dev.yml`, `docker-compose.prod.yml`).
- Service images built in CI, published to Ameritas's internal registry, pulled by tag.
- Persistent volumes for Postgres and uploaded files; Redis is ephemeral.
- Horizontal scaling of Celery workers is achieved by `docker compose up --scale worker=N` and (when needed) by adding additional worker VMs that share the same broker.
- Reverse proxy: Nginx on the front VM, terminating TLS via Ameritas certificate management.
- Health checks: each service exposes `/healthz`; Compose restart policy `unless-stopped`.
- Backups: Postgres dumps to S3-compatible store nightly + WAL archival.
- This decision is **revisitable** if any of: (a) traffic grows beyond what 2-3 worker VMs handle, (b) Synthia goes multi-tenant, (c) Ameritas standardizes on Kubernetes for all tools.

## Consequences

**Positive**
- Minimal operator-skill surface; on-call rotation can reason about Compose, `docker logs`, and `systemctl`.
- Fast local dev parity: same `docker-compose.dev.yml` developers use runs the production topology.
- No Kubernetes control-plane cost or learning tax for a small team.
- Backups, monitoring, and TLS reuse existing Ameritas VM patterns.

**Negative / Tradeoffs**
- No native autoscaling, rolling updates, or self-healing across nodes. Failover is manual or scripted.
- Horizontal scaling beyond a few worker VMs becomes awkward — at that scale a real orchestrator wins.
- Some best-practice tooling (Helm charts, k8s operators) is unavailable; we reinvent some patterns in scripts.

**Neutral**
- Service boundaries remain orchestrator-agnostic: a future migration to Kubernetes is mostly a packaging exercise, not a redesign.

## Alternatives Considered

- **Kubernetes (EKS / AKS / on-prem).** Rejected for now (over-engineered for current scale).
- **Nomad.** Rejected (uncommon in Ameritas; would need a learning investment with little payoff over Compose).
- **Bare systemd units on VMs.** Rejected (loses dev/prod parity that containerization gives).
- **Single-VM monolith without Docker.** Rejected (kills isolation between Celery workers and the API, complicates rollbacks).

## Related

- Related to: ADR-0012 (Celery worker scaling), ADR-0013 (single-tenant), ADR-0010 (pluggable storage)
- References: `docker-compose.dev.yml`, `docker-compose.prod.yml`, `docs/DEPLOYMENT.md`
