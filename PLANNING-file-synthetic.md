# File-Based Synthetic Data Generation — Planning

> Extension of existing synthetic data feature to support file output formats (CSV, flat file, VSAM, columnar) driven by schema metadata, data dictionaries, and sample datasets.

---

## Summary

Add a file output layer to DataWrangler's synthetic data generation. Users define schemas via COBOL copybook upload, Excel data dictionary, manual UI builder, or existing discovery metadata. Optionally provide a format-matched sample file to improve data fidelity. Generate synthetic data into CSV, fixed-width flat files, VSAM (fixed/variable, EBCDIC/COMP-3), or columnar (Parquet/ORC) formats. Multi-file generation in one run with cross-file referential integrity and mixed formats. Output delivered as zip download.

---

## Decisions Log

| # | Decision | Answer |
|---|----------|--------|
| 1 | Copybook parser | Custom parser + existing library fallback |
| 2 | EBCDIC encoding | Full mainframe-compatible (CP037/CP1140, COMP-3, COMP) + ASCII fixed-width |
| 3 | Output delivery | Zip download from UI |
| 4 | Data dictionary format | Excel (.xlsx) |
| 5 | File set naming | User-defined per file + auto-generated fallback |
| 6 | Sample upload format | Must match target format |

---

## Phase 1: Schema Parsers & Internal Model

### Goal
Unified `FileSchemaDefinition` model that all schema sources produce and all writers consume.

### Tasks

#### 1.1 — FileSchemaDefinition Domain Model
- **File:** `backend/app/domain/synthetic/file_schema.py`
- New value objects:
  - `FileSchemaDefinition` — fields, format, encoding, record length, RDW flag
  - `FileFieldDefinition` — name, type, length, start_position, decimal_places, encoding (ASCII/EBCDIC), comp_type (none/COMP/COMP-3), nullable, pii_type, fk_reference
  - `FileFormat` enum — `CSV`, `FIXED_WIDTH`, `VSAM_FIXED`, `VSAM_VARIABLE`, `PARQUET`, `ORC`
  - `EncodingType` enum — `ASCII`, `EBCDIC_CP037`, `EBCDIC_CP1140`, `UTF8`
- Add `FileSetDefinition` — list of `FileSchemaDefinition` with cross-file FK declarations

#### 1.2 — COBOL Copybook Parser
- **File:** `backend/app/infrastructure/parsers/copybook_parser.py`
- Parse PIC clauses → `FileFieldDefinition`
  - `PIC X(n)` → alphanumeric, length n
  - `PIC 9(n)` → numeric, length n
  - `PIC 9(n)V9(m)` → decimal, n integer + m decimal digits
  - `PIC S9(n) COMP-3` → packed decimal
  - `PIC S9(n) COMP` → binary
  - REDEFINES, OCCURS (single-level), FILLER
  - Level numbers (01-49, 77, 88)
- Custom parser as primary, fallback to `cobollang` or `copybook` library if available
- Output: `FileSchemaDefinition`

#### 1.3 — Excel Data Dictionary Parser
- **File:** `backend/app/infrastructure/parsers/excel_dictionary_parser.py`
- Accept `.xlsx` upload with expected columns:
  - field_name, data_type, length, start_position (optional), decimal_places, nullable, pii_type, fk_reference, comp_type
- Header row auto-detection (fuzzy match column names)
- Validation: missing required fields, type checking, position overlap detection
- Output: `FileSchemaDefinition`

#### 1.4 — Upload API Endpoints
- **File:** `backend/app/api/v1/synthetic.py` (extend)
- `POST /projects/{project_id}/synthetic/file-schemas/upload-copybook` — multipart file upload
- `POST /projects/{project_id}/synthetic/file-schemas/upload-dictionary` — multipart .xlsx upload
- `POST /projects/{project_id}/synthetic/file-schemas/manual` — JSON body with field definitions
- `POST /projects/{project_id}/synthetic/file-schemas/from-discovery` — pull from existing discovery metadata by table name
- `GET /projects/{project_id}/synthetic/file-schemas` — list saved schemas
- All return `FileSchemaDefinition` JSON

---

## Phase 2: File Writers

### Goal
Writer implementations for all five output formats.

### Tasks

#### 2.1 — Writer Base Class
- **File:** `backend/app/infrastructure/writers/base_writer.py`
- `BaseFileWriter` ABC:
  - `write(schema: FileSchemaDefinition, data: list[dict], output_path: Path) -> Path`
  - `get_extension() -> str`
  - `validate_schema(schema) -> list[str]` (format-specific validation)

#### 2.2 — CSV Writer
- **File:** `backend/app/infrastructure/writers/csv_writer.py`
- Configurable: delimiter, quote char, header row, encoding, line terminator
- Handles None/NULL values

#### 2.3 — Fixed-Width Writer
- **File:** `backend/app/infrastructure/writers/fixed_width_writer.py`
- ASCII encoding
- Right-pad alphanumeric (spaces), left-pad numeric (zeros)
- Configurable pad character, record terminator (newline or none)

#### 2.4 — VSAM Writer (Fixed + Variable)
- **File:** `backend/app/infrastructure/writers/vsam_writer.py`
- EBCDIC encoding (CP037 default, CP1140 option)
- COMP-3 packed decimal encoding: BCD nibbles + sign nibble
- COMP binary encoding: big-endian 2/4/8 byte integers
- Fixed-length mode: constant record size, no RDW
- Variable-length mode: 4-byte RDW prefix (record length + 4, big-endian)
- Signed numeric handling (trailing overpunch or separate sign)
- No record terminator (binary format)

#### 2.5 — Columnar Writer (Parquet/ORC)
- **File:** `backend/app/infrastructure/writers/columnar_writer.py`
- Parquet via `pyarrow` (already likely a dependency)
- ORC via `pyarrow.orc`
- Map FileFieldDefinition types → Arrow types
- Configurable compression (snappy, gzip, zstd, none)

#### 2.6 — Writer Registry
- **File:** `backend/app/infrastructure/writers/registry.py`
- `FileFormat` → writer class mapping
- Factory method: `get_writer(format: FileFormat) -> BaseFileWriter`

---

## Phase 3: Sample File Parsing & Profiling

### Goal
Parse sample files in their native format, profile distributions for guided generation.

### Tasks

#### 3.1 — Sample File Parsers
- **File:** `backend/app/infrastructure/parsers/sample_file_parser.py`
- Read sample files using the same schema definition:
  - CSV → `pandas.read_csv` with schema-derived dtypes
  - Fixed-width → `pandas.read_fwf` with positions from schema
  - VSAM → custom binary reader (EBCDIC decode, COMP-3 unpack) → DataFrame
  - Parquet/ORC → `pyarrow` → DataFrame
- Sample must match target format (per decision #6)
- Output: `pandas.DataFrame`

#### 3.2 — Distribution Profiler
- **File:** `backend/app/infrastructure/engine/distribution_profiler.py`
- Profile each column from sample DataFrame:
  - Numeric: min, max, mean, std, distribution fit (normal, lognormal, uniform)
  - Categorical: value frequencies, cardinality
  - String patterns: regex pattern detection (e.g., `POL-\d{4}-[A-Z]{2}`)
  - Null rate per column
  - Date/timestamp ranges and granularity
- Profile cross-column correlations (reuse from existing `QualityEvaluator` logic)
- Output: `ProfileResult` with per-column and cross-column stats

#### 3.3 — Profile-Guided Faker Integration
- **File:** `backend/app/infrastructure/engine/faker_engine.py` (extend)
- Accept optional `ProfileResult` to constrain generation:
  - Numeric: sample from fitted distribution instead of uniform random
  - Categorical: sample with learned frequencies
  - String: generate from learned regex pattern
  - Null: apply learned null rate
  - Correlations: preserve via conditional sampling where feasible

#### 3.4 — Sample Upload Endpoints
- **File:** `backend/app/api/v1/synthetic.py` (extend)
- `POST /projects/{project_id}/synthetic/file-schemas/{schema_id}/upload-sample` — multipart file
- `GET /projects/{project_id}/synthetic/file-schemas/{schema_id}/profile` — returns profiling result
- Validates sample format matches schema format

---

## Phase 4: Multi-File Generation & Orchestration

### Goal
Generate multiple files with cross-file FK integrity in one run, bundle as zip.

### Tasks

#### 4.1 — FileSetOrchestrator
- **File:** `backend/app/infrastructure/engine/file_set_orchestrator.py`
- Input: `FileSetDefinition` (multiple schemas with FK links)
- Topological sort across file schemas (reuse Kahn's algorithm from FakerEngine)
- Generate parent files first, collect FK values
- Pass FK value pools to child file generation
- Handle mixed formats (each file can be different format)

#### 4.2 — Zip Bundler
- **File:** `backend/app/infrastructure/writers/zip_bundler.py`
- Collect all written files → single zip
- User-defined filenames or auto-generated (`{schema_name}.{ext}`)
- Include optional manifest file (JSON: file list, schemas, row counts, generation metadata)

#### 4.3 — Celery Task Extension
- **File:** `backend/app/infrastructure/messaging/synthetic_tasks.py` (extend)
- New task: `run_file_generation_task(file_set_id, project_id, job_id)`
- Flow: load FileSetDefinition → load optional profiles → orchestrate → write files → zip → store → update job
- Zip stored in configured storage path (local or cloud)
- Job result includes download URL

#### 4.4 — Download Endpoint
- **File:** `backend/app/api/v1/synthetic.py` (extend)
- `GET /projects/{project_id}/synthetic/jobs/{job_id}/download` — stream zip file
- Content-Disposition: attachment with meaningful filename

---

## Phase 5: Frontend — File Output Mode

### Goal
UI for schema definition, sample upload, file set configuration, and zip download.

### Tasks

#### 5.1 — File Output Tab
- **File:** `frontend/src/app/projects/[projectId]/synthetic/page.tsx` (extend)
- New tab: "File Output" alongside existing database-targeted mode
- Tab shows: Schema Source → File Set Builder → Sample Upload → Generate → Download

#### 5.2 — Schema Source Selector
- **File:** `frontend/src/components/synthetic/schema-source-selector.tsx`
- Four options: Upload Copybook | Upload Excel Dictionary | Manual Builder | From Discovery
- Copybook/Excel: file upload dropzone with format validation
- Manual: column builder table (add/remove/reorder fields, set all field properties)
- Discovery: select from discovered tables, pull schema

#### 5.3 — File Set Builder
- **File:** `frontend/src/components/synthetic/file-set-builder.tsx`
- Add multiple output files to the set
- Per file: name (editable), format selector, row count, schema assignment
- FK relationship editor: visual link between files/columns
- Format-specific options per file (EBCDIC code page, CSV delimiter, compression, etc.)

#### 5.4 — Sample Upload
- **File:** `frontend/src/components/synthetic/sample-upload.tsx`
- Per-schema sample file upload (format must match target)
- Show profiling results after upload (distributions, patterns, null rates)
- Toggle: schema-only / sample-guided / sample-trained mode

#### 5.5 — Generation & Download
- **File:** `frontend/src/components/synthetic/file-generation-panel.tsx`
- Generate button → dispatches file generation job
- Progress tracking (reuse existing job polling)
- Download zip button on completion
- Generation summary: files generated, row counts, formats, file sizes

#### 5.6 — Zustand Store Extension
- **File:** `frontend/src/stores/synthetic-store.ts` (extend)
- New state: `fileSchemas`, `fileSets`, `sampleProfiles`, `fileGenerationJobs`
- Actions: `uploadCopybook`, `uploadDictionary`, `createManualSchema`, `uploadSample`, `generateFileSet`, `downloadZip`

---

## Dependencies

| Package | Purpose | Phase |
|---------|---------|-------|
| `openpyxl` | Excel data dictionary parsing | 1 |
| `pyarrow` | Parquet/ORC read + write | 2, 3 |
| `ebcdic` (or custom) | EBCDIC encoding/decoding | 2, 3 |
| `cobollang` (optional) | Copybook parser fallback | 1 |
| `scipy.stats` | Distribution fitting for profiler | 3 |

---

## Estimated Scope

| Phase | Backend | Frontend | Total |
|-------|---------|----------|-------|
| 1 — Schema Parsers | 4 tasks | 0 | ~2-3 days |
| 2 — File Writers | 6 tasks | 0 | ~3-4 days |
| 3 — Sample Parsing & Profiling | 4 tasks | 0 | ~2-3 days |
| 4 — Orchestration | 4 tasks | 0 | ~2 days |
| 5 — Frontend | 0 | 6 tasks | ~3-4 days |
| **Total** | **18 tasks** | **6 tasks** | **~12-16 days** |

---

## Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| COMP-3 encoding edge cases (signs, odd-length) | Comprehensive test suite with known mainframe outputs |
| COBOL copybook dialect variations | Custom parser covers 80% cases, library fallback for edge cases |
| Large VSAM sample parsing performance | Cap sample at 50K records (consistent with existing statistical engine) |
| Cross-file FK with mixed EBCDIC/ASCII encoding | FK values stored as Python native types, encoded only at write time |
