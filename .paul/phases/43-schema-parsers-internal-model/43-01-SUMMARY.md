---
phase: 43-schema-parsers-internal-model
plan: 01
subsystem: domain
tags: [cobol, copybook, vsam, ebcdic, comp-3, file-schema, ddd, value-objects]

requires:
  - phase: none
    provides: first plan of v0.7 milestone

provides:
  - FileSchemaDefinition domain model (unified file schema contract)
  - FileFieldDefinition frozen value object
  - FileSetDefinition with cross-file FK declarations
  - CrossFileFK frozen value object
  - FileFormat, EncodingType, CompType enums
  - CopybookParser (COBOL copybook → FileSchemaDefinition)

affects: [44-file-writers, 45-sample-profiling, 46-orchestration, 47-frontend, 43-02-excel-api]

tech-stack:
  added: []
  patterns: [frozen-dataclass-value-objects, to_dict-from_dict-serialization, input-size-guards]

key-files:
  created:
    - backend/app/domain/synthetic/file_schema.py
    - backend/app/infrastructure/parsers/__init__.py
    - backend/app/infrastructure/parsers/copybook_parser.py
  modified:
    - backend/app/domain/synthetic/value_objects.py

key-decisions:
  - "FileFieldDefinition and CrossFileFK are frozen dataclasses for domain immutability"
  - "comp_type and file_format stored as string values (not enum instances) for serialization simplicity"
  - "fk_reference stored as tuple (not dict) in FileFieldDefinition for frozen compatibility, serialized as dict in to_dict()"
  - "PIC editing symbols (Z, *, $) rejected with ValueError rather than silently handled"

patterns-established:
  - "to_dict()/from_dict() on all domain value objects for JSON persistence"
  - "Input size guards on all parser entry points (1MB / 10K lines)"
  - "Error messages from parsers include line numbers and offending content"
  - "validate() returns list[str] of errors (not exceptions) for batch reporting"

duration: ~15min
completed: 2026-04-04
---

# Phase 43 Plan 01: FileSchemaDefinition Domain Model + Copybook Parser Summary

**Pure DDD domain model for file-based synthetic schemas (6 value objects, 3 enums) and a COBOL copybook parser handling PIC X/9, COMP, COMP-3, REDEFINES, OCCURS with line-numbered errors.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~15min |
| Completed | 2026-04-04 |
| Tasks | 2 completed |
| Files created | 3 |
| Files modified | 1 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: FileSchemaDefinition domain model complete and framework-free | Pass | All fields, enums, zero framework imports verified |
| AC-2: FileSetDefinition supports multi-file FK declarations | Pass | Cross-file FK validation, mixed formats per schema |
| AC-3: Copybook parser handles standard PIC clauses | Pass | PIC X, 9, S9, V, COMP, COMP-3, FILLER, REDEFINES, OCCURS, level 88 skip |
| AC-4: Copybook parser computes field positions automatically | Pass | Sequential positions, correct record_length, VSAM_FIXED + EBCDIC defaults |
| AC-5: Parser rejects malformed and oversized input | Pass | 1MB/10K line guard, line-numbered errors, nested OCCURS rejection |
| AC-6: Field name uniqueness and serialization | Pass | Duplicate detection, byte_length validation, to_dict/from_dict round-trip |

## Accomplishments

- FileSchemaDefinition as the unified contract all schema sources produce and all file writers consume — foundation for entire v0.7
- COBOL copybook parser with correct COMP-3 byte length calculation: `ceil((total_digits + 1) / 2)`
- 5-rule validate() method: position overlaps, byte_length <= 0, duplicate names, record_length consistency, format/encoding compatibility
- Full to_dict()/from_dict() serialization for all domain objects — ready for JSONB persistence in plan 43-02

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `backend/app/domain/synthetic/file_schema.py` | Created | FileFieldDefinition, FileSchemaDefinition, CrossFileFK, FileSetDefinition |
| `backend/app/domain/synthetic/value_objects.py` | Modified | Added FileFormat, EncodingType, CompType enums |
| `backend/app/infrastructure/parsers/__init__.py` | Created | Package marker |
| `backend/app/infrastructure/parsers/copybook_parser.py` | Created | CopybookParser class |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Frozen dataclasses for FileFieldDefinition, CrossFileFK | Domain immutability per DDD value object convention | FileSchemaDefinition is NOT frozen (fields list is mutable during parser construction) |
| Store comp_type/file_format as string values, not enum instances | Simplifies serialization — frozen dataclasses can't hold mutable enum references cleanly | Consumers compare against enum `.value` strings |
| fk_reference as tuple not dict | Frozen dataclass compatibility (dicts aren't hashable) | to_dict() converts to {"file": ..., "field": ...}, from_dict() accepts both |
| Reject unrecognized PIC symbols (Z, *, $, comma) | These are display-format editing symbols, not data fields — silently accepting them produces wrong byte lengths | Users with report copybooks get clear error; can extend later if needed |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Essential correctness fix |
| Deferred | 0 | — |

**Total impact:** One essential fix during qualification, no scope creep.

### Auto-fixed Issues

**1. PIC Symbol Validation Missing**
- **Found during:** Task 2 qualification
- **Issue:** `PIC Z(5)9` was silently accepted as numeric (Z expanded then counted as chars), producing wrong field type and byte length
- **Fix:** Added PIC symbol allowlist validation (`9XAVSP`) before type detection. Unrecognized symbols raise ValueError with line number.
- **Files:** `backend/app/infrastructure/parsers/copybook_parser.py`
- **Verification:** `PIC Z(5)9` now raises `ValueError: Invalid PIC clause 'Z(5)9' at line 4: Unrecognized PIC symbol(s): Z`

## Issues Encountered

None.

## Next Phase Readiness

**Ready:**
- FileSchemaDefinition is the complete contract for plan 43-02 (Excel parser, API endpoints, persistence)
- to_dict()/from_dict() ready for JSONB serialization in persistence layer
- CopybookParser ready to be called from upload-copybook API endpoint

**Concerns:**
- None

**Blockers:**
- None — plan 43-02 can proceed immediately

---
*Phase: 43-schema-parsers-internal-model, Plan: 01*
*Completed: 2026-04-04*
