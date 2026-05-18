---
phase: 44-file-writers
plan: 03
subsystem: infrastructure, api
tags: [parquet, orc, pyarrow, registry, file-formats, api]

requires:
  - phase: 44-file-writers
    plan: 01
    provides: BaseFileWriter, write_atomic, CSVWriter, FixedWidthWriter
  - phase: 44-file-writers
    plan: 02
    provides: VSAMWriter

provides:
  - ColumnarWriter (Parquet + ORC via pyarrow)
  - WriterRegistry + default_registry singleton + get_writer factory
  - GET /api/v1/file-formats endpoint (auth-gated, returns all 6 formats)
  - 15 unit tests (9 columnar + 6 registry)

affects: [45-sample-profiling, 46-orchestration, 47-frontend]

tech-stack:
  added: [pyarrow>=18.0.0]
  patterns:
    - "Lazy pyarrow imports inside ColumnarWriter so the writer module imports cleanly even if pyarrow is briefly unavailable"
    - "Module-level registry singleton; create_default_registry() builds a fresh registry when needed"
    - "Capability-driven registration via writer_cls.supported_formats()"

key-files:
  created:
    - backend/app/infrastructure/writers/columnar_writer.py
    - backend/app/infrastructure/writers/registry.py
    - backend/app/api/v1/file_formats.py
    - backend/tests/unit/test_columnar_writer.py
    - backend/tests/unit/test_writer_registry.py
  modified:
    - backend/app/api/v1/__init__.py     # include file_formats_router
    - backend/pyproject.toml             # +pyarrow>=18.0.0

key-decisions:
  - "Reject signed display + binary + packed_decimal fields in ColumnarWriter (analytics output is decimal128/int/string; mainframe-binary encoding stays in VSAMWriter)."
  - "decimal_places > 0 with comp_type=='comp' is mapped to decimal128, not int — preserves scale for analytics."
  - "Registry collision check uses identity, not class name; re-registering the same class is a no-op."
  - "/file-formats endpoint placed in its own file_formats.py router (no project_id prefix); registered via api/v1/__init__.py."

duration: ~30min
completed: 2026-05-16
---

# Phase 44 Plan 03: ColumnarWriter + Registry + /file-formats endpoint Summary

**Parquet + ORC writers, the writer registry, and the API surface that
exposes registered formats to the future Phase 47 UI.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~30min |
| Completed | 2026-05-16 |
| Tasks | 5 of 5 |
| Files created | 5 |
| Files modified | 2 (api/v1/__init__.py, pyproject.toml) |
| Unit tests added | 15 (9 columnar + 6 registry) |
| Full suite | 123/123 passing |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Parquet round-trip via pyarrow | Pass | Decimal128 quantization preserved; None round-trips |
| AC-2: ORC round-trip via pyarrow | Pass | pyarrow.orc.read_table verified |
| AC-3: Deterministic Arrow type mapping | Pass | decimal128 / int32 / int64 / string per branch |
| AC-4: Registry resolves all 6 FileFormat values | Pass | 6/6 isinstance checks |
| AC-5: Class-driven registration via supported_formats | Pass | Collision raises ValueError; identity-based check |
| AC-6: GET /api/v1/file-formats | Pass | 200 with all 6 formats including label/extension/writer |

## Deviations from Plan

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | pyarrow was not in pyproject.toml — added and installed |
| Plan-doc errata | 1 | Plan suggested attaching the endpoint to the synthetic router; the cleanest implementation was a dedicated `file_formats.py` router registered in `api/v1/__init__.py` |

### Auto-fixed

**1. pyarrow dependency missing**
- **Found during:** verification step for Task 1
- **Issue:** Plan assumed pyarrow was already a transitive dep; container didn't have it.
- **Fix:** Added `pyarrow>=18.0.0` to `backend/pyproject.toml` and `pip install`-ed into the running backend image.
- **Files:** backend/pyproject.toml

## Phase 44 — full milestone closure

| Plan | Status | Tests added | Highlights |
|------|--------|-------------|------------|
| 44-01 | ✅ | 21 | BaseFileWriter ABC + write_atomic + CSVWriter + FixedWidthWriter |
| 44-02 | ✅ | 33 | EBCDIC codec + COBOL encoders + VSAMWriter (fixed + variable + RDW) |
| 44-03 | ✅ | 15 | ColumnarWriter + WriterRegistry + GET /api/v1/file-formats |

**69 unit tests added across Phase 44; 123 total backend unit tests green.**

The full writer abstraction is now:
- `BaseFileWriter` ABC with crash-safe `write_atomic` helper
- 4 concrete writers covering 6 file formats
- A registry that surfaces `FileFormat → writer class` and is callable through
  `get_writer(fmt)` or the singleton `default_registry()`
- A REST endpoint listing supported formats for the UI

## Contract for Phase 45 / 46 / 47

- **Phase 45 (Sample profiling)**: build parsers that *read* the same formats
  the writers produce. The Arrow type mapping in ColumnarWriter is the
  authoritative source for Parquet/ORC schema inference round-trips.
- **Phase 46 (Orchestration)**: program against `registry.get_writer(fmt)`;
  never instantiate writers directly. Use `write_atomic` for any side files.
- **Phase 47 (Frontend)**: drive the format dropdown from
  `GET /api/v1/file-formats`. Each entry's `writer` field is for debug
  display only; UI logic should branch on `value`.

## Next Phase Readiness

**Plan 44-03 complete. Phase 44 (File Writers) is fully shipped.**

Ready for Phase 45 — Sample File Parsing & Distribution Profiling.

---
*Phase: 44-file-writers, Plan: 03*
*Completed: 2026-05-16*
