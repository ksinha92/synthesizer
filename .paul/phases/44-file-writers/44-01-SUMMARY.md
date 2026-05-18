---
phase: 44-file-writers
plan: 01
subsystem: infrastructure
tags: [writers, file-io, csv, fixed-width, atomic-write, abc]

requires:
  - phase: 43-schema-parsers-internal-model
    provides: FileSchemaDefinition, FileFieldDefinition, FileFormat, EncodingType

provides:
  - BaseFileWriter ABC (write / get_extension / supported_formats abstracts; validate_schema + _ensure_writable concrete)
  - write_atomic contextmanager (tmp-file-then-os.replace, unlink on exception)
  - CSVWriter (RFC 4180, configurable delimiter/quote/encoding/header/BOM)
  - FixedWidthWriter (position-correct ASCII, implied_decimal toggle, REDEFINES handling, signed-fields rejection)
  - 21 unit tests (8 CSV + 13 fixed-width)
  - CopybookParser now sets schema.metadata["implied_decimal"]=True (carried forward from this plan's Codex fix)

affects: [44-02-vsam, 44-03-columnar-registry, 45-sample-profiling, 46-orchestration]

tech-stack:
  added: []
  patterns:
    - "Atomic file write via tmp-file-then-os.replace contextmanager"
    - "Writer ABC with class-method capability declaration (supported_formats)"
    - "Schema validation before any bytes — _ensure_writable gate"

key-files:
  created:
    - backend/app/infrastructure/writers/__init__.py
    - backend/app/infrastructure/writers/base_writer.py
    - backend/app/infrastructure/writers/csv_writer.py
    - backend/app/infrastructure/writers/fixed_width_writer.py
    - backend/tests/unit/test_csv_writer.py
    - backend/tests/unit/test_fixed_width_writer.py
  modified:
    - backend/app/infrastructure/parsers/copybook_parser.py  # implied_decimal metadata flag

key-decisions:
  - "BaseFileWriter abstract surface restricted to {write, get_extension, supported_formats}; validate_schema is a concrete delegate to schema.validate() so writers don't reimplement domain rules."
  - "write_atomic is a module-level contextmanager (not a BaseFileWriter method) so the helper is callable from any writer without inheritance gymnastics."
  - "implied_decimal lives on schema.metadata, not on FileFieldDefinition — keeps the domain value object frozen and adds the toggle at the boundary where format conventions are decided."
  - "FixedWidthWriter rejects signed numeric/decimal + binary/packed_decimal at validate time and points users to VSAMWriter (Plan 44-02). COBOL overpunch sign encoding is genuinely a VSAM-family concern."
  - "CopybookParser now sets schema.metadata['implied_decimal']=True because every COBOL decimal is implied — this keeps 'copybook upload → fixed-width output' working without extra UI."

patterns-established:
  - "Writer contract: sync method, schema-first validation, atomic write via write_atomic, returns the path written"
  - "Format-specific imports stay inside their writer file; base_writer.py imports only stdlib + domain"
  - "Tests assert byte-exact output for fixed-width formats; round-trip equality for CSV via csv.DictReader"

duration: ~45min including Codex stop-gate fix
completed: 2026-05-16
---

# Phase 44 Plan 01: BaseFileWriter + CSVWriter + FixedWidthWriter Summary

**Writer abstraction (ABC + atomic write helper) and the two ASCII text writers.
Round-trip readable, schema-validated, crash-safe.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~45min (including Codex stop-gate fix) |
| Completed | 2026-05-16 |
| Tasks | 4 of 4 + 1 stop-gate fix |
| Files created | 6 |
| Files modified | 1 (copybook_parser.py, +3 lines) |
| Unit tests added | 21 (all passing) |
| Full suite | 75/75 passing, no regressions |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: BaseFileWriter ABC contract | Pass | Exactly 3 abstracts; validate_schema concrete delegate |
| AC-2: write_atomic crash-safe rename | Pass | Tmp-then-os.replace; unlink on exception; verified by tests |
| AC-3: CSVWriter RFC 4180 compliance | Pass | Delimiter/quote/encoding/BOM all configurable; None→empty; decimal_places honored |
| AC-4: FixedWidthWriter position-correct | Pass | Byte-exact assertions, filler + REDEFINES handled |
| AC-5: Schema validation before bytes | Pass | Both writers raise ValueError before opening any file |
| AC-6: Round-trip readable | Pass | CSV via csv.DictReader; fixed-width via byte slicing |
| AC-7: Sync writers, output_path honored | Pass | No async; returned Path equals input |

## Accomplishments

- Writer package landed at `backend/app/infrastructure/writers/` with zero
  format-specific imports in `base_writer.py`.
- `write_atomic` contextmanager provides the crash-safety primitive every
  future writer (VSAM in 44-02, Columnar in 44-03) will reuse.
- `CSVWriter` ships with BOM toggle, configurable line terminator, and
  decimal-places-aware float serialization.
- `FixedWidthWriter` handles REDEFINES (target's bytes occupy the position;
  the REDEFINES alias is skipped on emit), filler fields, and the implied-
  decimal toggle COBOL-derived schemas need.
- 21 unit tests including atomic-write-failure simulation (mock injection
  on the third row → output_path must not exist after exception).
- Codex stop-gate addressed: signed numeric/decimal fields produced by
  CopybookParser now flow through to FixedWidthWriter with a clear,
  actionable rejection rather than silently-wrong bytes.

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `backend/app/infrastructure/writers/__init__.py` | Created | Package marker |
| `backend/app/infrastructure/writers/base_writer.py` | Created | BaseFileWriter ABC + write_atomic |
| `backend/app/infrastructure/writers/csv_writer.py` | Created | CSVWriter |
| `backend/app/infrastructure/writers/fixed_width_writer.py` | Created | FixedWidthWriter + signed-fields rejection (44-02 boundary) |
| `backend/tests/unit/test_csv_writer.py` | Created | 8 CSV tests including atomic-exception |
| `backend/tests/unit/test_fixed_width_writer.py` | Created | 13 fixed-width tests including 4 Codex-fix tests |
| `backend/app/infrastructure/parsers/copybook_parser.py` | Modified | Set schema.metadata["implied_decimal"]=True |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Codex stop-gate fix |
| Deferred | 0 | — |

### Auto-fixed Issues

**1. Signed-fields + copybook decimal handling (Codex stop-gate)**
- **Found during:** stop-time review after initial APPLY
- **Issue:** Plan's leading-sign logic assumed `byte_length = digits + 1` but the
  copybook parser sets `byte_length = digits` for signed display numerics (COBOL
  overpunch convention). Also, parser-produced schemas had no implied_decimal
  flag, causing FixedWidthWriter to emit a literal `.` in COBOL decimal fields.
- **Fix:** FixedWidthWriter now rejects signed numeric/decimal + binary/packed_decimal
  fields at validate_schema time with a clear "use VSAMWriter (Plan 44-02)" error.
  CopybookParser now sets `schema.metadata["implied_decimal"] = True`.
- **Files:** fixed_width_writer.py, copybook_parser.py, test_fixed_width_writer.py
- **Verification:** 4 new tests (rejection of signed numeric, signed decimal,
  packed_decimal; copybook→FixedWidthWriter round-trip with implied decimal).

## Contract for downstream plans

44-02 (VSAM) and 44-03 (Columnar + Registry) MUST:
- Subclass `BaseFileWriter`.
- Use `write_atomic` for output; never open `output_path` directly.
- Implement `supported_formats()` as a class method returning a `set[FileFormat]`.
- Run domain validation via `super().validate_schema(schema)` and append
  format-specific checks (as `FixedWidthWriter` does with its signed-field rule).
- Stay sync; Phase 46's Celery task is the async layer.

44-02 specifically picks up the signed-fields / COBOL-overpunch work this plan
intentionally deferred — see the rejection message in
`FixedWidthWriter.validate_schema` for the contract.

44-03 introduces the `WriterRegistry` and `get_writer(format)` factory; the
writers from this plan should not need modification to plug in.

## Next Phase Readiness

**Plan 44-01 complete. Ready for Plan 44-02 (VSAMWriter — EBCDIC + COMP-3 + RDW).**

The writer abstraction is stable; VSAMWriter is purely a new subclass with
no upstream changes required.

---
*Phase: 44-file-writers, Plan: 01*
*Completed: 2026-05-16*
