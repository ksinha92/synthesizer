# File Loader Wizard + Enterprise File Viewer — Design

**Status:** Approved scope (full enhancement + multi-record-layout support)
**Audience:** DataWrangler analysts who work with mainframe-derived files
**Design reference:** Micro Focus File Manager, BMC Compuware File-AID, IBM File Manager for z/OS, JRecord (Bruce Martin), Altova MapForce / Talend Data Mapper

---

## Problem

The File Viewer tab the previous task shipped surfaces uploaded file schemas, but there is no UI in the application to *upload* them. The placeholder copy tells users to "upload a copybook or Excel dictionary…under the project's Synthetic page" — a flow that does not exist. The four backend endpoints (`upload-copybook`, `upload-dictionary`, `manual`, `from-discovery`) are unreachable from the browser. Sample-data validation is also unreachable — `sample_file_parser` is production-ready but no endpoint exposes it.

In addition, mainframe analysts expect:
1. A **viewer** that surfaces COBOL-style metadata (offset / length / PIC clause / COMP type) per field and a record-by-record sample browser
2. **Multi-record-layout** support — copybooks with multiple 01-levels selected per record by a discriminator field (`RECORD-TYPE = 'A' → Header layout`)
3. **Cross-file relationship auto-mapping** with confidence scoring
4. **Data dictionary mapping** between two schemas with transforms

This spec covers all four, plus the missing wizard, in one pass.

---

## Goals

- Drive every existing file-schema endpoint from the browser without rebuilding backend behavior already in place
- Add the four genuinely new backend capabilities (preview, suggest-relationships, dictionary-mapper, multi-layout) the wizard needs
- Reuse the app's existing wizard / dialog / form patterns (`CreateProjectWizard`, `AccessibleDialog`, `FormField`, `SchemaTree`)
- Stay within the 500-LOC-per-file project rule by splitting the wizard and viewer into focused components

## Non-Goals

- Hex byte-level editing of records (Microfocus has this — skip it; this is a read/inspect surface, not a record editor)
- `OCCURS DEPENDING ON` — parser limitation; surface a warning when detected
- ML-blended FK discovery — rule-based heuristics with optional value-overlap sampling are good enough for v1
- A full expression / XSLT language in the dictionary mapper — 6 built-in transforms only

---

## User Flow

```
Project page
   └─ Database View → File Viewer tab
        │
        ├─ "Add file schema" button (toolbar)
        │    └─ ┌────────── FileLoaderWizard (modal) ──────────┐
        │      │ 1. Source: copybook | xlsx | manual | discovery │
        │      │ 2. Parse: editable field grid, parser warnings  │
        │      │ 3. Sample (optional): drop data file → preview  │
        │      │ 4. Confirm                                       │
        │      └──────────────────────────────────────────────────┘
        │
        ├─ Schema list (left)
        ├─ File Schema Viewer (center)
        │    ├─ Layout switcher (when multi-record)
        │    ├─ Structure tree (offset / length / PIC / PII / FK)
        │    └─ Sample data grid (formatted ↔ character toggle)
        ├─ Field detail panel (right)
        └─ Toolbar:
             ├─ "Suggest relationships" → SuggestRelationshipsModal
             ├─ "Map to dictionary" → DictionaryMapperModal
             └─ "Reload sample"
```

---

## Backend Changes

### 1. Extend `FileSchemaDefinition` with `layout_variants` (backward-compatible)

`backend/app/domain/synthetic/file_schema.py`:

```python
@dataclass
class LayoutCondition:
    """A single layout-selection rule: <field> <op> <value>."""
    field_name: str          # name of a field in the base layout (e.g. "RECORD_TYPE")
    operator: str            # "eq" | "ne" | "in" | "starts_with"
    value: str | list[str]   # scalar for eq/ne/starts_with; list for "in"


@dataclass
class LayoutVariant:
    """A conditional layout applied when its conditions match a record."""
    name: str                            # human label, e.g. "HeaderRecord"
    fields: list[FileFieldDefinition]    # full field list for records that match
    conditions: list[LayoutCondition]    # ALL must match (AND semantics)


@dataclass
class FileSchemaDefinition:
    name: str
    fields: list[FileFieldDefinition]       # acts as the BASE layout
    file_format: str
    encoding: str = "ascii"
    record_length: int = 0
    has_rdw: bool = False
    output_filename: str | None = None
    metadata: dict = field(default_factory=dict)
    # NEW — optional. Empty → schema is single-layout (existing behavior).
    layout_variants: list[LayoutVariant] = field(default_factory=list)
```

The persistence layer stores `layout_variants` inside the existing `metadata` JSONB column under key `"layout_variants"` — no schema migration required. `FileSchemaDefinition.to_dict()` / `from_dict()` carry the variants through, and the `SQLAlchemyFileSchemaRepository._to_dict` helper exposes them as a top-level `layout_variants` key on responses so the frontend doesn't need to dig into `metadata`.

**Sample data is ephemeral** — preview requests stream the uploaded data file through `sample_file_parser`, return the parsed first N rows, and discard the file. The bytes themselves are never persisted to the database; only the schema is.

### 2. Copybook parser split strategies

`backend/app/infrastructure/parsers/copybook_parser.py`:

```python
class SplitStrategy(str, Enum):
    SINGLE = "single"             # current behavior: flatten everything
    SPLIT_01_LEVEL = "split_01"   # one LayoutVariant per 01-level entry
    SPLIT_REDEFINE = "split_redefine"  # one LayoutVariant per REDEFINES branch
```

The `parse()` method gains a `strategy: SplitStrategy = SINGLE` parameter. The upload endpoint accepts a query param `split_strategy=split_01|split_redefine|single` and forwards it. When `SPLIT_01_LEVEL` is selected and the copybook only has one 01-level, behavior degrades to `SINGLE`.

Record-type assignment for the auto-generated variants happens in a follow-up call from the wizard (see step 2 of the wizard) — the parser cannot know what discriminator field to use.

### 3. `POST /file-schemas/{schema_id}/preview`

`backend/app/api/v1/file_schema_preview.py` (new router):
- Multipart upload of a real data file
- Calls `sample_file_parser.parse(temp_path, schema_definition, limit=N)`
- For multi-layout schemas, evaluates each record against every variant's `conditions`; assigns the first matching variant or `"_base"` if none match
- Returns:
  ```json
  {
    "rows": [
      {"layout": "HeaderRecord", "fields": {"RECORD_TYPE": "H", ...},
       "raw_bytes": "<hex>", "errors": []},
      ...
    ],
    "summary": {"matched": 199, "unmatched": 1,
                "errors_per_field": {"AMOUNT": 0, ...}}
  }
  ```
- Max file size 50 MB; cap rows at 1000

### 4. `POST /file-schemas/suggest-relationships`

`backend/app/domain/synthetic/relationship_suggester.py` (new pure helper) + `backend/app/api/v1/file_schema_relationships.py` (new router):

For every pair `(schema_a, schema_b)` in the project, score every `(field_a, field_b)` pair:

| Signal | Weight | How |
|---|---|---|
| Name similarity | 0.4 | Damerau-Levenshtein on normalized identifiers (strip prefix/suffix `_id`, lowercase, separator-normalize) |
| Type compatibility | 0.2 | data_type + length+ decimal_places agree → 1.0; same family (numeric vs alphanumeric) → 0.5; else 0 |
| Cardinality hint | 0.1 | If field is `is_primary_key` on either side, boost |
| Value overlap | 0.3 | Optional: when both sides have a stored sample, compute |child ∩ parent| / |child|; require ≥ 0.3 sample size |

Returns:
```json
{
  "suggestions": [
    {"source_file": "ORDERS", "source_field": "CUSTOMER_ID",
     "target_file": "CUSTOMERS", "target_field": "ID",
     "score": 0.87,
     "evidence": {"name_similarity": 0.95,
                  "type_compatibility": 1.0,
                  "value_overlap": 0.92,
                  "cardinality_match": true},
     "sample_size": 1000}
  ]
}
```

Confidence threshold and bulk-accept happen on the client; the server returns every suggestion above a low floor (default 0.4).

### 5. Data Dictionary Mapper

`backend/app/api/v1/file_schema_mapper.py` (new router):

`POST /file-schemas/{id}/derive` — body is the mapping:

```json
{
  "target_name": "ORDERS_FOR_LEGACY_SYSTEM",
  "target_format": "fixed_width",
  "target_encoding": "ebcdic_cp037",
  "mappings": [
    {"target_field": "CUST_NM",
     "source_field": "customer_name",
     "transforms": [{"type": "upper"}, {"type": "pad", "args": {"length": 30, "side": "right", "char": " "}}]},
    ...
  ]
}
```

Transforms (6 built-ins): `trim`, `pad`, `upper`, `lower`, `substring`, `date_format`. Lookup tables (`code_to_text`) deferred to v2 — adds storage complexity.

Result is a brand-new `FileSchemaDefinition` saved via existing `FileSchemaRepository`, with `metadata.derived_from = source_schema_id` and `metadata.mappings = [...]` so re-edits round-trip.

---

## Frontend Changes

### Components

```
frontend/src/components/file-loader/
  ├── upload-file.ts                      ← multipart helper (sibling of `api`)
  ├── types.ts                            ← shared interfaces
  ├── wizard/
  │   ├── file-loader-wizard.tsx          ← AccessibleDialog shell + state machine
  │   ├── step-source.tsx
  │   ├── step-parse.tsx                  ← editable grid + parser warnings
  │   ├── step-sample.tsx                 ← drag-drop + preview
  │   └── step-confirm.tsx
  ├── viewer/
  │   ├── file-schema-viewer.tsx          ← 3-pane shell
  │   ├── schema-structure-tree.tsx       ← offset/length/PIC/PII/FK badges
  │   ├── sample-data-grid.tsx            ← formatted ↔ character toggle
  │   ├── layout-switcher.tsx             ← multi-record variant picker
  │   └── field-detail-panel.tsx          ← right-rail field metadata
  ├── relationships/
  │   ├── suggest-relationships-modal.tsx
  │   └── evidence-chip.tsx
  └── dictionary/
      ├── dictionary-mapper-modal.tsx
      ├── mapping-row.tsx
      └── transform-pill.tsx
```

### Wiring into existing pages

- `frontend/src/app/projects/[projectId]/database/page.tsx` File Viewer tab: replace empty-state copy with an actionable button that opens `FileLoaderWizard`. When schemas exist, the tab also exposes the viewer + the two modals via a toolbar.
- The wizard launch button also appears on the `/projects/[projectId]/synthetic/page.tsx` "File output" tab so users can reach it from either place.

### `uploadFile()` helper

`api.post` in `use-api.ts` forces `Content-Type: application/json`. A new sibling `uploadFile()` exported alongside `api` accepts a `FormData` body and lets the browser set the boundary header. It still respects the 401-refresh flow and includes credentials.

### Multi-record-layout UI

- **Wizard parse step:** when the copybook parser returns multiple 01-levels, ask the user once: "This copybook has N record layouts. Treat as a single flat layout, split per 01-level, or split per REDEFINES?" and forward the choice.
- **Discriminator step (only for split):** small inline UI to pick the discriminator field + operator + value for each variant. Saved into `layout_variants[].conditions`.
- **Viewer:** layout-switcher tab strip above the structure tree (`Base | HeaderRecord | DetailRecord | …`). Each tab shows that variant's fields; the sample grid colors rows by which variant matched.

---

## Testing

| Layer | Test |
|---|---|
| Backend unit | `LayoutVariant` JSON round-trip; copybook parser SPLIT_01_LEVEL emits one variant per 01-level; relationship_suggester scores name+type+value-overlap correctly with stub data; preview endpoint returns per-record layout assignment |
| Backend integration | `POST /file-schemas/{id}/preview` happy path + bad-file path |
| Frontend tsc | new components type-clean |
| Manual smoke | upload a sample COPYBOOK with two 01-levels → wizard prompts split → viewer shows tab strip → sample drop highlights row colors |

---

## Out of Scope (deferred)

- `OCCURS DEPENDING ON` runtime expansion
- Lookup-table transforms in the dictionary mapper
- Hex byte editing in the viewer
- Versioning of file schemas (current schema is overwritten by re-edit; analyst-grade tools usually keep history)
- ML-blended FK discovery
