---
phase: 43-schema-parsers-internal-model
plan: 02
subsystem: infrastructure, api
tags: [excel, dictionary, parser, file-schema, api, persistence, jsonb]

requires:
  - phase: 43-01
    provides: FileSchemaDefinition, FileFieldDefinition, CopybookParser, enums

provides:
  - ExcelDictionaryParser (Excel .xlsx → FileSchemaDefinition)
  - FileSchemaRepository ABC
  - FileSchemaModel (SQLAlchemy, JSONB fields)
  - SQLAlchemyFileSchemaRepository
  - 5 file-schema API endpoints (upload-copybook, upload-dictionary, manual, from-discovery, list)

affects: [44-file-writers, 45-sample-profiling, 46-orchestration, 47-frontend]

tech-stack:
  added: [openpyxl]
  patterns: [fuzzy-header-matching, dict-based-repository, multipart-upload]

key-files:
  created:
    - backend/app/infrastructure/parsers/excel_dictionary_parser.py
    - backend/app/domain/synthetic/file_schema_repository.py
    - backend/app/infrastructure/persistence/models/file_schema.py
    - backend/app/infrastructure/persistence/sqlalchemy/file_schema_repo.py
  modified:
    - backend/app/api/v1/synthetic.py
    - backend/pyproject.toml

key-decisions:
  - "FileSchemaRepository uses dict in/out (not entity) since FileSchemaDefinition is a value object, not an entity"
  - "from-discovery endpoint queries DiscoveredSchemaModel → DiscoveredTableModel → DiscoveredColumnModel chain (plan assumed single DiscoveryResultModel)"
  - "Excel parser uses openpyxl read_only=True for memory efficiency"
  - "FileSchemaModel stores fields as JSONB array for flexible schema evolution"

patterns-established:
  - "Fuzzy column alias matching for Excel header detection (case-insensitive, space/underscore tolerant)"
  - "Helper functions _schema_dict_to_detail_response() and _schema_definition_to_save_dict() for endpoint/persistence bridge"
  - "File upload endpoints use UploadFile + File(...) pattern with parser delegation"

duration: ~20min
completed: 2026-04-06
---

# Phase 43 Plan 02: Excel Dictionary Parser + API Endpoints + Persistence Summary

**Excel data dictionary parser with fuzzy header detection, JSONB-backed file schema persistence, and 5 REST endpoints completing all four schema input sources (copybook, Excel, manual, discovery).**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~20min |
| Completed | 2026-04-06 |
| Tasks | 2 completed |
| Files created | 4 |
| Files modified | 2 |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: Excel parser produces FileSchemaDefinition | Pass | Fuzzy header matching, type mapping, comp_type, auto-position, empty row skip |
| AC-2: All four schema source endpoints | Pass | upload-copybook, upload-dictionary, manual, from-discovery, list — all 5 routes registered |
| AC-3: File schemas persisted with full metadata | Pass | JSONB fields, retrieve by ID, list by project_id, timestamps |

## Accomplishments

- ExcelDictionaryParser with 9-column fuzzy alias matching, scanning first 5 rows for headers
- Type normalization covering 20+ input type strings → 5 canonical types
- FileSchemaRepository ABC (dict-based, not entity-based — fits value object pattern)
- FileSchemaModel with JSONB fields column for flexible schema storage
- 5 API endpoints: upload-copybook, upload-dictionary, manual JSON entry, from-discovery, list
- from-discovery correctly walks the 3-level discovery model chain (schema → table → columns)

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `backend/app/infrastructure/parsers/excel_dictionary_parser.py` | Created | ExcelDictionaryParser class |
| `backend/app/domain/synthetic/file_schema_repository.py` | Created | FileSchemaRepository ABC |
| `backend/app/infrastructure/persistence/models/file_schema.py` | Created | FileSchemaModel (SQLAlchemy) |
| `backend/app/infrastructure/persistence/sqlalchemy/file_schema_repo.py` | Created | SQLAlchemyFileSchemaRepository |
| `backend/app/api/v1/synthetic.py` | Modified | 5 new file-schema endpoints + Pydantic models |
| `backend/pyproject.toml` | Modified | Added openpyxl>=3.1.0 dependency |

## Decisions Made

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Dict-based repository (not entity) | FileSchemaDefinition is a value object; wrapping with id/timestamps at persistence layer avoids domain pollution | Save/get return plain dicts; endpoints handle Pydantic conversion |
| Fix from-discovery to use actual discovery models | Plan assumed DiscoveryResultModel (doesn't exist); real schema uses 3-table chain | Endpoint queries DiscoveredSchemaModel → DiscoveredTableModel → DiscoveredColumnModel |
| openpyxl read_only=True | Memory efficiency for large dictionaries | Cannot write; read-only is fine for parser use case |
| metadata_ column name (with underscore) | Avoids collision with SQLAlchemy's internal metadata attribute | Mapped to "metadata" in DB via mapped_column("metadata", ...) |

## Deviations from Plan

### Summary

| Type | Count | Impact |
|------|-------|--------|
| Auto-fixed | 1 | Essential correctness fix |
| Deferred | 0 | — |

**Total impact:** One schema model fix during implementation, no scope creep.

### Auto-fixed Issues

**1. Discovery Model Mismatch**
- **Found during:** Task 2 implementation
- **Issue:** Plan assumed a single `DiscoveryResultModel` with `project_id` and `table_name` columns and a `columns` JSONB field. Actual schema uses `DiscoveredSchemaModel` → `DiscoveredTableModel` → `DiscoveredColumnModel` chain.
- **Fix:** Rewrote from-discovery endpoint to query the 3-model chain: find schema by connection_id, find table by name within schema, load columns from table.
- **Files:** `backend/app/api/v1/synthetic.py`
- **Verification:** Endpoint correctly queries all three discovery models.

## Issues Encountered

None.

## Next Phase Readiness

**Phase 43 complete.** Both plans (43-01 + 43-02) delivered:
- FileSchemaDefinition domain model + all enums
- CopybookParser + ExcelDictionaryParser
- Full persistence layer (model + repository)
- All 5 API endpoints

**Ready for Phase 44: File Writers**
- FileSchemaDefinition is the contract writers will consume
- Persistence layer ready for writer integration
- No blockers

---
*Phase: 43-schema-parsers-internal-model, Plan: 02*
*Completed: 2026-04-06*
