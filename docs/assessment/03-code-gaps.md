# 03 — Code Gaps Audit

**Scope:** Read-only static audit of `backend/`, `frontend/src/`, `cli/` for incomplete, stubbed, or dead code.
**Method:** ripgrep pattern scans + file-by-file inspection of suspect hits.
**Inventory:** 225 backend `.py` files, 165 frontend `.ts/.tsx` files, 3 CLI `.py` files.
**Auditor:** code-auditor, 2026-05-17.

---

## Executive Summary — Gap Counts by Type

| Gap type                                                  | Count | Severity skew |
|-----------------------------------------------------------|------:|---------------|
| `raise NotImplementedError` (deliberate guard rails)      | 4     | None — intentional |
| `raise NotImplementedError` (real stubs)                  | 0     | n/a |
| Functions with only `pass` body (real stubs)              | 2     | Medium |
| `# TODO`/`# FIXME` markers (action-bearing)               | 2     | Medium |
| Domain modules that are empty placeholder files           | 3     | High (DDD claim) |
| Unused/dead production modules                            | 2     | Medium |
| Mocked-but-not-implemented runtime paths                  | 2     | **Critical** |
| Frontend `// TODO` / `console.log` left-overs             | 0     | n/a |
| CLI stubs                                                 | 0     | n/a |
| Bounded contexts missing a domain repository ABC          | 3 / 7 | Medium |
| Bounded contexts missing a domain service                 | 3 / 7 | Medium |

The codebase is **substantially more complete than typical** for a TDM platform at this scope. The two **critical** gaps are: (1) masking preview returns results computed against an empty dataset, and (2) subsetting silently drops user-provided WHERE filters. Both are silent failures, not exceptions, so the UI shows green checks while the feature is dead.

---

## 1. Python — `raise NotImplementedError`

All four hits are deliberate **guard rails** that ship with explicit "not a stub" comments, intended to fail loud on a malformed schema or unsupported COBOL `data_type`. **No real stubs.**

| # | File:line | Context |
|---|-----------|---------|
| 1 | `backend/app/infrastructure/writers/columnar_writer.py:102` | `ColumnarWriter cannot map data_type {dt!r}` — guard for Parquet/ORC mapping. Comment at L93 explicitly says "Guard rail (not a stub)." |
| 2 | `backend/app/infrastructure/writers/fixed_width_writer.py:160` | `FixedWidthWriter cannot render data_type {data_type!r}` — flat-file writer rejects COMP/COMP-3/binary so the caller gets a 422. |
| 3 | `backend/app/infrastructure/writers/vsam_writer.py:137` | `VSAMWriter cannot render data_type {data_type!r}` — VSAM writer rejects unknown EBCDIC types. |
| 4 | `backend/app/infrastructure/parsers/sample_file_parser.py:169` | `parse_vsam cannot decode data_type {field.data_type!r}` — symmetric guard on the parse side. |

**Verdict:** Defensible. These pair with reciprocal validations (write-side rejects what parse-side can't decode), so they don't surface to users as "feature missing" gaps — they surface as 422s on bad input.

---

## 2. Python — Functions with only `pass` body

Of the 21 `pass` occurrences in `backend/app/`, **only two are stubs**; the remaining 19 are legitimate (exception swallows inside `try/except`, empty exception classes with docstring, or `pass` after a docstring on a dataclass/event).

| # | File:line | Snippet | Severity |
|---|-----------|---------|----------|
| 1 | `backend/app/infrastructure/persistence/sqlalchemy/masking_repo.py:31-32` | `async def delete(self, entity_id: uuid.UUID) -> None:\n    pass` | Low — no API endpoint deletes a masking policy yet, so the stub isn't reachable. But the method advertises a contract it doesn't honor. |
| 2 | `backend/app/infrastructure/persistence/sqlalchemy/discovery_repo.py:53-54` | `async def delete(self, entity_id: uuid.UUID) -> None:\n    pass  # Cascade delete handled by DB` | **Medium** — comment claims cascade delete but `DiscoveredSchemaModel` does **not** declare `ondelete="CASCADE"` (only `ephemeral.py` and `webhook_delivery.py` do). If this method is ever wired to an endpoint, rows will leak. |

**Sample of legitimate `pass` (NOT counted as stubs):** `backend/app/api/v1/connections.py:192` (cleanup after `writer.wait_closed()`), `backend/app/infrastructure/messaging/celery_app.py:95,133,215,233` (best-effort observability), `backend/app/infrastructure/writers/base_writer.py:94,101` (atomic-write fallback), `backend/app/domain/connection/events.py:13` (empty dataclass body).

---

## 3. Python — `# TODO` / `# FIXME` / `# XXX` / `# HACK`

Only **two** action-bearing TODOs in production code; the other hits are doc-string examples (`X(10) -> XXXXXXXXXX`).

| # | File:line | Note |
|---|-----------|------|
| 1 | `backend/app/infrastructure/auth/jwt.py:14` | `# TODO: Use RS256/ES256 with asymmetric keys in production instead of HS256` — security debt. Doesn't break the feature, but undermines any production deployment story. |
| 2 | `backend/app/infrastructure/engine/subsetting_engine.py:128` | `# TODO: Apply WHERE filter at DB level instead of fetching all` — see Section 5 below. **This is the symptom of a critical silent-failure bug.** |

---

## 4. Python — Empty placeholder domain modules

Three "domain service" modules contain **only a docstring**, contradicting the project's stated DDD bounded-context completeness.

| # | File | Size | Status |
|---|------|------|--------|
| 1 | `backend/app/domain/compliance/services.py` | 1 line | Empty — no service class. |
| 2 | `backend/app/domain/masking/services.py` | 1 line | Empty — no service class. |
| 3 | `backend/app/domain/subsetting/services.py` | 1 line | Empty — no service class. |

The corresponding business logic lives in `application/<ctx>/handlers.py` and `infrastructure/engine/*.py`. This is not broken behavior, but it makes the **DDD bounded-context claim partially true**: the contexts have entities + handlers but ship with hollow domain-services. (`discovery`, `synthetic`, `workflow`, `connection` all have non-trivial domain services.)

---

## 5. Mocked-but-not-implemented runtime paths (CRITICAL)

Two paths claim to deliver a feature but quietly return wrong/empty data.

### 5a. Masking Preview returns results against an empty dataset

**File:** `backend/app/application/masking/handlers.py:82-83`

```python
# Placeholder sample data — real implementation reads from connector
return engine.mask_preview([], rule_dicts, limit=5)
```

The preview handler passes `[]` (empty rows) to `MaskingEngine.mask_preview`. The engine will dutifully apply rules to zero rows and return an empty list. **The user's "preview" UI will always render no data**, regardless of the actual table contents or rule effects. There is no code path that reads sample rows from the source connector inside the preview flow.

**Impact:** `POST /projects/{id}/masking/policies/{policy_id}/preview` is broken end-to-end. UI is showing a stubbed feature.

### 5b. Subsetting silently drops WHERE filters

**File:** `backend/app/infrastructure/engine/subsetting_engine.py:120-128`

```python
if table_name in root_names:
    root_cfg = next((r for r in config.root_tables if r["table_name"] == table_name), {})
    where = root_cfg.get("where_filter", "")
    validated_where = self._validate_where(where)
    rows = await connector.get_sample_data(schema, table_name, limit=config.target_row_count or 10000)
    # TODO: Apply WHERE filter at DB level instead of fetching all
```

`validated_where` is computed and then **never used**. `connector.get_sample_data()` is called without any filter, so the entire root table (up to `target_row_count`) is fetched. The downstream traversal happens on this unfiltered set, which defeats the whole point of subsetting by criteria.

**Impact:** `POST /projects/{id}/subset/configs/{id}/execute` claims it honors WHERE clauses; in reality the clause is parsed, validated, and discarded.

### Honorable mention (lower severity)

`backend/app/application/synthetic/handlers.py:61` — `PreviewHandler` passes `schema_metadata = {"relationships": []}` to the FakerEngine. The engine still generates real Faker output, but FK relationships are not honored in the preview output. Acceptable for "preview" semantics; flag for product review.

---

## 6. Dead code

### 6a. Unused production module — `connection/schema_drift.py`

**File:** `backend/app/domain/connection/schema_drift.py` (67 lines)

Defines `SchemaFingerprint`, `fingerprint(...)`, `assert_no_drift(...)`, `SchemaDriftDetected`. **No production caller imports this module.** Only `backend/tests/unit/test_schema_drift.py` references it.

The matching UI toggle `block_on_schema_change` is exposed by `infrastructure/connectors/registry.py:105,125` (kwargs accepted) and `block_on_schema_change_enabled(extra_params)` reads it back — but no call site actually invokes `assert_no_drift` before running discovery/masking. The drift gate the docs/UI promise is **fully dead code**.

### 6b. Unused service — `ConnectionTestService`

**File:** `backend/app/domain/connection/services.py:10-23`

```python
class ConnectionTestService:
    async def test_connection(self, connection: Connection) -> bool:
        # Placeholder — actual connector implementation injected in infrastructure layer
        try:
            connection.status = ConnectionStatus.CONNECTED  # Always sets to CONNECTED
            connection.add_event(ConnectionTested(aggregate_id=connection.id))
            return True
        except Exception:
            ...
```

`rg ConnectionTestService backend/app` returns only the definition. No call site. The real test logic lives in `application/connection/handlers.py:62-93`, which calls `connector.test_connection()` directly. The placeholder always returns `True` and would be misleading if anyone wired it up.

### 6c. Misleading no-op delete with stale comment

`backend/app/infrastructure/persistence/sqlalchemy/discovery_repo.py:53-54` — see Section 2; comment claims "Cascade delete handled by DB" but no FK has `ondelete="CASCADE"` for the discovered schema model.

---

## 7. Frontend (`frontend/src/`) — TypeScript/TSX

Scanned 165 `.ts/.tsx` files.

| Check                                  | Hits | Result |
|----------------------------------------|------|--------|
| `// TODO` / `// FIXME` / `// HACK`     | 0    | Clean. |
| `console.log` left-overs               | 0    | Only `console.error(...)` in `catch` blocks (legitimate). |
| `throw new Error("not implemented")`   | 0    | None. All `throw new Error(...)` raise real HTTP errors. |
| Empty `{}` returns where logic expected| 0    | None. |
| `alert()`/`prompt()` dev leftovers     | 1    | `frontend/src/components/projects/project-list.tsx:79` uses `prompt()` for clone-name capture — intentional UX, not dev leftover. |

**Verdict:** Frontend is clean of stubs and TODO debris.

---

## 8. CLI (`cli/datawrangler/`) — Python

Three files, 214 lines total. Zero `TODO`/`FIXME`/`NotImplementedError`/`pass`-only function bodies.

**Verdict:** Clean.

---

## 9. Bounded-Context Completeness Matrix

Legend: **Y** = present + non-trivial; **·** = file exists but empty/trivial; **N** = file does not exist; **Y\*** = present but mirrored in infra layer.

| Bounded context | Entities | Value objects | Domain events | Domain repo ABC | Domain service | Application handlers | Infrastructure repo | API endpoints |
|-----------------|:--------:|:-------------:|:-------------:|:---------------:|:--------------:|:--------------------:|:-------------------:|:-------------:|
| **connection**  | Y | Y | Y | Y (`repository.py`) | Y (unused stub class — see 6b) | Y | Y (`connection_repo.py`) | Y (`connections.py`, 518 LOC) |
| **discovery**   | Y | Y | Y | Y (`repository.py`) | Y (`services.py`, 221 LOC) | Y | Y (`discovery_repo.py`, no-op delete) | Y (`discovery.py`, 265 LOC) |
| **masking**     | Y | Y | Y | Y (`repository.py`) | · (1-line file) | Y (preview is stubbed — 5a) | Y (no-op delete) | Y (`masking.py`, 210 LOC) |
| **synthetic**   | Y | Y | Y | Y (`repository.py` + `file_schema_repository.py`) | Y (ABC, 25 LOC) | Y | Y (`synthetic_repo.py`, `file_schema_repo.py`) | Y (`synthetic.py`, 415 LOC + 555 LOC for file schemas) |
| **subsetting**  | Y | N (no `value_objects.py`) | Y | **N** (no domain repo ABC) | · (1-line file) | Y | Y (concrete repo only) | Y (`subsetting.py`, 185 LOC; engine drops WHERE — 5b) |
| **workflow**    | Y | N (no `value_objects.py`) | Y | **N** (no domain repo ABC) | Y (`services.py`, 137 LOC) | Y | Y (concrete repo only) | Y (`workflows.py`, 147 LOC) |
| **compliance**  | Y | N (no `value_objects.py`) | Y | **N** (no domain repo ABC) | · (1-line file) | Y | Y (concrete repo only) | Y (`compliance.py`, 155 LOC) |

**Completeness % (out of 8 columns, treating · and N as missing):**

| Context     | Score | % |
|-------------|------:|---:|
| connection  | 8/8 minus unused service stub | **94%** |
| discovery   | 8/8 (delete is broken but exists) | **94%** |
| synthetic   | 8/8 | **100%** |
| masking     | 7/8 (empty services) | **88%** |
| workflow    | 6/8 (no VO, no domain repo ABC) | **75%** |
| compliance  | 5/8 (no VO, no domain repo ABC, empty services) | **63%** |
| subsetting  | 5/8 (no VO, no domain repo ABC, empty services) | **63%** |

The three weakest contexts (`workflow`, `compliance`, `subsetting`) share the same shape: they were added later, they skipped the domain repository ABC, they skipped the value-object module, and their domain-services file is a placeholder. The infrastructure repos work, but they do **not** implement an abstract contract — so swapping them out for a fake in tests requires duck-typing rather than implementing an interface.

---

## 10. Top 20 Highest-Priority Gaps

Ranked by **(impact on a user-facing feature claim) × (silence — whether the failure is invisible)**.

| # | Gap | File:line | Severity | Blocks |
|---|-----|-----------|----------|--------|
| 1 | Masking preview computes against empty dataset (silent) | `backend/app/application/masking/handlers.py:82` | **Critical** | Masking preview UI |
| 2 | Subsetting silently drops WHERE filters (silent) | `backend/app/infrastructure/engine/subsetting_engine.py:126-128` | **Critical** | Subsetting by criteria |
| 3 | `schema_drift` module entirely unused; `block_on_schema_change` toggle is dead | `backend/app/domain/connection/schema_drift.py` (whole file) | High | Schema-drift gating feature claim |
| 4 | JWT uses HS256 with shared secret | `backend/app/infrastructure/auth/jwt.py:14` | High | Production deployment / multi-tenant |
| 5 | `ConnectionTestService` is a placeholder that always returns True; correct code path lives elsewhere | `backend/app/domain/connection/services.py:13-23` | Medium | Domain-layer integrity claim |
| 6 | `discovery_repo.delete()` is `pass` with misleading "cascade" comment, no FK actually cascades | `backend/app/infrastructure/persistence/sqlalchemy/discovery_repo.py:53-54` | Medium | Future delete endpoint will silently leak |
| 7 | `masking_repo.delete()` is `pass` (no policy DELETE endpoint yet) | `backend/app/infrastructure/persistence/sqlalchemy/masking_repo.py:31-32` | Medium | Future DELETE endpoint |
| 8 | Subsetting has no domain repository ABC (only concrete repo) | `backend/app/domain/subsetting/` (missing `repository.py`) | Medium | DDD/testability claim |
| 9 | Workflow has no domain repository ABC | `backend/app/domain/workflow/` (missing `repository.py`) | Medium | DDD/testability claim |
| 10 | Compliance has no domain repository ABC | `backend/app/domain/compliance/` (missing `repository.py`) | Medium | DDD/testability claim |
| 11 | Compliance has no value-objects module | `backend/app/domain/compliance/` (missing `value_objects.py`) | Low | DDD completeness |
| 12 | Subsetting has no value-objects module | `backend/app/domain/subsetting/` (missing `value_objects.py`) | Low | DDD completeness |
| 13 | Workflow has no value-objects module | `backend/app/domain/workflow/` (missing `value_objects.py`) | Low | DDD completeness |
| 14 | `domain/compliance/services.py` is a 1-line placeholder | `backend/app/domain/compliance/services.py` | Low | DDD bounded-context completeness |
| 15 | `domain/masking/services.py` is a 1-line placeholder | `backend/app/domain/masking/services.py` | Low | DDD bounded-context completeness |
| 16 | `domain/subsetting/services.py` is a 1-line placeholder | `backend/app/domain/subsetting/services.py` | Low | DDD bounded-context completeness |
| 17 | Synthetic preview ignores FK relationships (`{"relationships": []}`) | `backend/app/application/synthetic/handlers.py:61` | Low | Preview accuracy |
| 18 | Ephemeral context has no domain layer at all (acknowledged in module docstring) | `backend/app/infrastructure/messaging/ephemeral_tasks.py:16-19` | Low | DDD claim (explicitly noted as a stub by author) |
| 19 | `validated_where` computed then discarded — dead local variable inside #2 | `backend/app/infrastructure/engine/subsetting_engine.py:126` | Low | Code smell symptom of #2 |
| 20 | DI container only wires 14 of 25 API modules (`container.py:34-52`) — newer modules (privacy_hub, sensitivity_rules, schema_changes, ephemeral, webhooks, file_formats, generator_presets, synthetic_quality, synthetic_file_schemas, database_view) are not in `wiring_config` | `backend/app/container.py:34-52` | Low | `@inject` annotations on those routers will silently no-op |

---

## 11. What Looks Solid (Counter-Findings)

To balance the report — the following components are **fully implemented and not stubbed**, despite surface-level signals that might suggest otherwise:

- **Connectors:** All 9 SQL/Cloud/NoSQL connectors (`postgresql`, `mysql`, `oracle`, `db2`, `sqlserver`, `snowflake`, `redshift`, `databricks`, `mongodb`) are real client wrappers between 190–320 LOC each. Real `test_connection`, `get_schemas`, `get_sample_data` implementations against the actual driver.
- **LLM providers:** Both `ClaudeProvider` and `OllamaProvider` are real Anthropic-SDK / HTTP implementations. The abstract `LLMProvider` ABC uses `...` correctly (Protocol pattern), which is not a stub.
- **Synthetic engines:** `FakerEngine` (311 LOC), `StatisticalEngine` (229 LOC — real GaussianCopula/CTGAN), `LLMEngine` (209 LOC — real plan→Faker delegation) all generate.
- **PII detector:** Real 4-layer pipeline with Presidio + spaCy + regex + LLM fallback.
- **Masking engine:** Real `mask_preview` and `mask_rows` against the engine — the bug is at the **handler boundary** (passes `[]`), not in the engine.
- **Frontend:** Zero stubs, zero TODOs, zero `console.log` leftovers across 165 files. Real Zustand stores, real API hooks.
- **CLI:** 214 LOC, fully implemented, no debris.
- **Bounded-context entities + events:** All 7 contexts have non-trivial entities and event types.

The codebase is in better shape than the surface ripgrep counts suggest. The dangerous gaps are the **two silent-failure runtime paths** (5a, 5b), not the missing-file gaps.

---

## 12. Methodology Notes

- Scanned `backend/app/` (production code) and `cli/`; `backend/tests/` and `node_modules/` excluded.
- `pass` matches in Python were filtered manually — 19 of 21 are legitimate exception swallows or empty event/dataclass bodies, not stubs.
- `...` (ellipsis) matches in Python are almost all in `@abstractmethod` / `Protocol` definitions — these are correct DDD idiom, not stubs.
- `NotImplementedError` matches in Python are all in writer/parser guard rails with explicit "not a stub" comments and matching reciprocal validation on the other side of the round-trip.
- All cited line numbers verified by reading the file at that offset.
