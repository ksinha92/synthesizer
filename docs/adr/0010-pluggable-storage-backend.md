# ADR-0010: Pluggable Storage Backend

- **Status:** Accepted (minimal ABC with Local FS + S3 selected by `STORAGE_BACKEND` env var, **DI-resolved as of 2026-05-17**); richer interface and `DatabaseBlobBackend` are **Proposed** extensions
- **Date:** 2026-05-17
- **Deciders:** Synthia core team
- **Tags:** storage, infrastructure, architecture

**Implementation status (2026-05-17):**

*Verified in code:*

- ABC: `StorageBackend` in `backend/app/infrastructure/storage/base.py` with five async methods — `save(path, data: bytes) -> str`, `load(path) -> bytes`, `delete(path) -> None`, `list(prefix="") -> list[str]`, `get_url(path) -> str`.
- Implementations: `LocalFilesystemStorage` (`local.py`, 49 lines), `S3Storage` (`s3.py`, 66 lines).
- Selection: single global setting `STORAGE_BACKEND: str = "local"  # local | s3` in `config.py`.
- `S3Storage.get_url` returns a presigned URL via `generate_presigned_url`; `LocalFilesystemStorage.get_url` returns `file://<absolute path>`.
- **DI-resolved `StorageBackend`** — `backend/app/container.py` exposes a `storage_backend = providers.Singleton(_build_storage_backend, settings=settings)` provider that selects the concrete class from `Settings.STORAGE_BACKEND`. Consumed by:
  - `backend/app/api/v1/compliance.py:download_report` via `@inject` + `Depends(Provide["storage_backend"])` (line ~135).
  - `backend/app/infrastructure/messaging/compliance_tasks.py:_run_report_generation_async` via `Container().storage_backend()` (line ~106).
  - `backend/app/infrastructure/messaging/subsetting_tasks.py:_run_async` via `Container().storage_backend()` (line ~136), replacing the prior inline `if STORAGE_BACKEND == "s3"` branch that called `S3Storage()` with no args (a latent crash if S3 were ever enabled).
  - Test: `backend/tests/unit/test_container_storage.py` parametrized over `local`/`s3`, asserting the container resolves to the correct concrete class.

*Explicitly not implemented (referenced in this ADR as design targets, not current state):*

- **No `DatabaseBlobBackend`** — only two backends exist.
- **No streaming I/O** — `save`/`load` take and return `bytes`. Large synthetic outputs (multi-GB) currently fit only via callers chunking and writing many objects.
- **No `metadata`, `exists`, `put_object_ref`, or `presign(ttl)` methods** — the interface is intentionally minimal.
- **No per-domain backend routing** — every caller uses the single configured backend.
- **`get_url` is not a uniform "mediated streaming URL"** — the S3 implementation presigns; the local implementation returns a `file://` path usable only from the same host. Callers must know which they got.
- **No strict validation of `STORAGE_BACKEND` values.** Anything other than `"s3"` silently falls back to `LocalFilesystemStorage`. Tightening to `Literal["local", "s3"]` is a candidate for a follow-up settings-validation ADR.

Treat the *Decision* section below as the **current minimal contract**, and the *Proposed extensions* section as the design target a future ADR can promote.

## Context

Synthia produces and consumes blob payloads:

- Uploaded source files for file-based discovery and synthetic generation.
- Generated synthetic datasets (often gigabytes per job).
- Job artifacts: discovery reports, masking previews, audit bundles.
- Statistical model snapshots for re-sampling without re-fitting.

Operational reality varies by environment:

- **Local dev** wants files on the developer's disk — no S3 mocking, no credentials.
- **CI** wants ephemeral, deterministic storage.
- **Production (Ameritas)** has an S3-compatible object store. Smaller datasets are simpler to keep colocated with metadata in Postgres BLOBs.

Hard-coding any single backend would make either dev velocity or prod alignment painful.

## Decision (current minimal contract — Accepted)

A `StorageBackend` ABC with the following five async methods is the interface every caller uses; the implementation in use is selected by the `STORAGE_BACKEND` env var (`local` or `s3`).

```python
class StorageBackend(ABC):
    async def save(self, path: str, data: bytes) -> str: ...
    async def load(self, path: str) -> bytes: ...
    async def delete(self, path: str) -> None: ...
    async def list(self, prefix: str = "") -> list[str]: ...
    async def get_url(self, path: str) -> str: ...
```

- **`LocalFilesystemStorage`** — files under a configurable `base_dir`; `get_url` returns `file://...`.
- **`S3Storage`** — boto3 against any S3-compatible endpoint (`AWS_ENDPOINT_URL` override supports Ameritas's internal object store and MinIO in tests); `get_url` returns a presigned URL with a fixed `PRESIGNED_URL_EXPIRY`.

**DI resolution.** Callers obtain `StorageBackend` from the DI container (`Container.storage_backend`), not by importing concrete classes. FastAPI routes use `@inject` + `Depends(Provide["storage_backend"])`; Celery tasks call `Container().storage_backend()` inside the task body (Singleton scope is per-container, which matches the per-worker lifetime).

## Proposed extensions (not yet decided)

A follow-up ADR should pick from or refine the items below; none of these are in current code.

- **Streaming I/O** (`save_stream` / `load_stream`) for multi-GB payloads; current `bytes` interface forces caller-side chunking.
- **`exists(path)`** for cheap presence checks without `load`.
- **Uniform mediated-download URL** for the Local backend (today returns raw `file://`, not safe to expose to clients).
- **`presign(path, ttl)`** as an explicit operation, distinct from `get_url`, so callers can request a time-limited URL with an explicit TTL on S3 and get an honest error on Local.
- **`DatabaseBlobBackend`** for small (<5 MB) artifacts where transactional colocation with job metadata simplifies semantics.
- **Per-domain backend routing** (e.g., archives → cheap S3 tier; live job artifacts → DB BLOB) instead of a single global setting.
- **Metadata on save** (`content_type`, custom tags) for audit and lifecycle policies.

Promotion of any of these requires the usual ADR cycle — a new ADR, code, and an updated `Implementation status` block here noting which extension landed.

## Consequences

**Positive (today)**
- Dev, CI, and prod use the same five-method contract with different backends; no S3 mocking needed for unit tests.
- Switching between Local and S3 is one env var, not a code change.
- The minimal ABC is small enough that audits and reviews can reason about it whole.

**Negative / Tradeoffs (today)**
- `bytes`-only I/O is a real limit for GB-scale synthetic outputs.
- No `exists` forces callers into try/`load`/catch patterns or external bookkeeping.
- Concrete-class imports in callers mean a future DI rewire will touch every call site.
- `get_url` semantics differ by backend (`file://` vs. presigned HTTPS); callers must not assume the URL is consumable off-host.
- Without per-domain routing, the same backend serves both small audit artifacts and large generated datasets — cost/latency tradeoffs cannot be tuned.

**Neutral**
- Encryption at rest remains the backend's responsibility (S3 SSE, disk encryption, future Postgres TDE).

## Alternatives Considered

- **S3-only, everywhere (including dev).** Rejected: forces cloud credentials or MinIO-in-Docker for offline work; slow inner loop.
- **Local FS only.** Rejected: doesn't match the Ameritas production object store.
- **Filesystem-as-S3 shim (s3fs, fuse).** Rejected: fragile, OS-specific, hides backend semantics.

## Related

- Related to: ADR-0008 (deployment), ADR-0013 (single-tenant — Ameritas-managed object store)
- References: `backend/app/infrastructure/storage/`, `backend/app/config.py` (`STORAGE_BACKEND`), DATAWRANGLER.md "File Storage"
