# Phase 44 Context — File Writers

> Discuss-phase output for **v0.7 File-Based Synthetic Data Generation**.
> Feeds `/paul:plan` for plans 44-01, 44-02, 44-03.

## Vision

Phase 43 shipped `FileSchemaDefinition` — the unified contract every schema
source produces (`copybook`, `excel dictionary`, `manual`, `from-discovery`).
Phase 44 is the **other half**: writer implementations that take a
`FileSchemaDefinition` plus a list of generated row dicts and produce a file
in the target format.

After this phase, DataWrangler can emit:
- **CSV** — configurable delimiter / quoting / encoding / line terminator.
- **Fixed-width ASCII** — position-based padding, optional record terminator.
- **VSAM fixed-length** — EBCDIC (CP037 default, CP1140 option), COMP-3
  packed decimal, COMP binary, signed-numeric handling. No RDW.
- **VSAM variable-length** — same VSAM rules + 4-byte big-endian RDW
  prefix per record.
- **Parquet / ORC** — Arrow-backed columnar, configurable compression
  (snappy / gzip / zstd / none).

The writer abstraction (registry + ABC) is what Phase 46 will orchestrate
across multiple files with cross-file FK integrity, and what Phase 45's
sample-file parsers will read back for profile validation.

## Goals (Phase 44)

1. **Common abstraction.** `BaseFileWriter` ABC defining the writer contract
   so format-specific writers compose cleanly. Method shape:
   `async write(schema, rows, output_path) -> Path`; helpers
   `get_extension() -> str`, `validate_schema(schema) -> list[str]`.
2. **Two ASCII writers** that ship together: CSV + Fixed-width.
3. **Mainframe-fidelity VSAM writer** for both fixed and variable record
   formats, with full EBCDIC + COMP-3 + COMP support and correct sign /
   pack / pad behavior. This is the high-risk area — see §4.
4. **Columnar writer** (Parquet + ORC) via pyarrow, with FileField type →
   Arrow type mapping that round-trips back through Phase 45's parsers.
5. **Writer registry.** `FileFormat → writer class` mapping with a
   `get_writer(format)` factory used by Phase 46's orchestrator and by the
   API to validate that a requested format is supported.
6. **Round-trip readable.** Every writer's output must be re-readable
   (CSV → pandas, fixed-width → pandas, VSAM → custom decode, columnar →
   pyarrow). Phase 45 builds the readers, but Phase 44 ships a
   round-trip unit test per writer to catch encoding bugs at build time.

Out of scope for Phase 44 (later phases):
- Sample-file parsers and distribution profiling (Phase 45).
- `FileSetOrchestrator` and multi-file FK integrity (Phase 46).
- Zip bundler + download endpoint (Phase 46).
- Frontend file-output UI (Phase 47).

## Plan breakdown (proposed)

| Plan | Scope | Notes |
| --- | --- | --- |
| **44-01** | `BaseFileWriter` ABC + `CSVWriter` + `FixedWidthWriter` + round-trip tests | Lowest risk. Establishes the writer module structure under `backend/app/infrastructure/writers/`. |
| **44-02** | `VSAMWriter` (fixed + variable), EBCDIC encode helpers, COMP-3 + COMP encoders, RDW framing | Highest risk. Needs property-based / golden-fixture tests against known-good output. |
| **44-03** | `ColumnarWriter` (Parquet + ORC via pyarrow) + Writer registry + factory + API surfacing | Wraps up the registry and exposes a `GET /file-formats` endpoint listing supported writers for the future UI. |

## Approach options considered

| Option | Summary | Recommendation |
| --- | --- | --- |
| A. One plan per writer (5 plans) | Maximum isolation; each writer ships independently. | Too many small plans; CSV + FixedWidth are tightly related (both ASCII / position-aware). Reject. |
| B. Two plans: ASCII set, then everything else | Bundle VSAM + columnar + registry together. | VSAM is the riskiest deliverable and warrants its own plan. Reject. |
| C. Three plans grouped by risk / family (this proposal) | ASCII writers / VSAM / columnar + registry. | **Recommended.** Matches roadmap. Lets us land 44-01 fast for momentum, gate 44-02 on mainframe-fidelity tests, finish with the lower-risk columnar work. |

## Constraints

- **DDD boundary.** Writers live in `infrastructure/writers/`. The domain
  layer (`FileSchemaDefinition`) is unchanged. No domain dependency on
  pyarrow, ebcdic codecs, etc.
- **No new top-level dependencies without justification.** Allowed:
  `pyarrow` (already in stack for columnar), Python stdlib `codecs`
  (ships with EBCDIC CP037 / CP1140 built in). Out: `ebcdic` package
  (third-party, smaller / less audited) unless stdlib coverage is
  inadequate.
- **Idempotent + crash-safe writes.** Writers write to a temp file under
  the target directory and `os.replace` on success so a partially-written
  file is never visible. This matters when Phase 46 wraps many writers
  in a single Celery task.
- **Schema validation before any bytes are written.** Each writer calls
  `validate_schema()` and refuses to start on errors (overlapping
  positions, bad COMP lengths, format/encoding mismatch).
- **No backward-compat shims.** Writers are net-new code; no migration
  concerns.

## Risk areas — VSAM-specific (44-02)

These are the parts that fail silently if implemented wrong:

1. **EBCDIC code page.** CP037 is the US default; CP1140 is the same with
   the Euro sign at byte `0x9F`. Field values are encoded character-by-char
   through `bytes.decode(...) / str.encode(...)` using the codec. Easy
   bug: forgetting to translate before zero/space padding.
2. **COMP-3 packed decimal.** Each digit is a 4-bit nibble; the final
   nibble is the sign (`C` positive, `D` negative, `F` unsigned). Length
   is `ceil((digits + 1) / 2)` bytes. A field declared `PIC S9(7)V99
   COMP-3` is 5 bytes, 9 digits + sign. Bugs: off-by-one on byte length,
   wrong sign nibble convention, wrong nibble order on odd-digit counts.
3. **COMP binary.** Big-endian, signed two's complement. Lengths from PIC:
   1–4 digits → 2 bytes, 5–9 → 4 bytes, 10–18 → 8 bytes. Bugs: little-
   endian, unsigned overflow, missing two's complement for negatives.
4. **Signed numeric (display).** For non-COMP signed numerics, the sign
   is encoded as an overpunch on the last digit in EBCDIC (`{` = +0,
   `A`–`I` = +1–9, `}` = −0, `J`–`R` = −1–9). Easy to forget when
   writing in ASCII/EBCDIC.
5. **RDW (Record Descriptor Word).** Variable-length records prepend a
   4-byte header: bytes 0-1 are record length **including the RDW**
   (big-endian), bytes 2-3 are zero. A 100-byte record's RDW is
   `0x00 0x68 0x00 0x00`. Easy bug: writing record length minus 4.
6. **No record terminator.** VSAM files have no newline / EOR marker;
   record boundaries are determined by fixed length or RDW. CSV / fixed-
   width habits will introduce silent corruption if writers leak `\n`.

**Mitigation:** plan 44-02 ships with golden-byte-string fixtures for at
least 8 representative records spanning all data types, both fixed and
variable mode, both code pages. Tests compare exact bytes, not parsed
values.

## Dependencies

- **Hard:** Phase 43 (FileSchemaDefinition + enums + repository). ✅ done.
- **Soft:** none. Phase 44 is a pure-Python infrastructure layer; no DB
  migrations, no API surface (except the small `GET /file-formats`
  endpoint in 44-03 which is a feature toggle, not a contract).
- **Downstream consumers:** Phases 45, 46, 47 each depend on a stable
  writer ABC + registry. Their plans should not start until 44-03 ships.

## Open questions (decide before /paul:plan)

1. **EBCDIC library choice.** Stdlib `codecs` supports `cp037` and
   `cp1140` natively. The third-party `ebcdic` package adds a few more
   pages but isn't needed unless Ameritas data uses CP500 / CP930 /
   CP1047. **Recommend stdlib unless a specific Ameritas dataset says
   otherwise.**
2. **Arrow type mapping for `decimal` fields.** Options: `decimal128`
   with explicit (precision, scale) from the field definition, or `float64`
   (lossy but cheap). UX-refactor uses `decimal128`. **Recommend decimal128.**
3. **CSV BOM.** Some Ameritas downstream tools expect a UTF-8 BOM; others
   reject it. Default to no BOM, expose as a `CSVWriter` option?
   **Recommend no BOM by default, configurable.**
4. **Variable-length VSAM block descriptors (BDW).** If output files are
   destined for mainframe upload, blocks may need BDW + RDW. Most file-
   transfer paths strip blocking. **Recommend RDW only; expose BDW as a
   later enhancement if real datasets need it.**
5. **Async vs sync writers.** Writers are CPU + I/O; making them `async`
   buys little (no parallelism per file). **Recommend sync writer
   methods called from the Celery task; the task itself runs async.**

These are flagged for you to confirm/adjust before `/paul:plan` for 44-01.

## Acceptance criteria

- [ ] `backend/app/infrastructure/writers/` module exists with `base_writer.py`,
      `csv_writer.py`, `fixed_width_writer.py`, `vsam_writer.py`,
      `columnar_writer.py`, `registry.py`.
- [ ] Each writer ships with at least one round-trip unit test (write →
      read → compare).
- [ ] VSAM writer ships with golden-byte fixture tests for at least 8
      records (mixed types, fixed + variable, CP037 + CP1140).
- [ ] `get_writer(format)` returns the correct class for every
      `FileFormat` enum value; unknown formats raise `NotFoundError`.
- [ ] `GET /api/v1/file-formats` returns the list of supported formats
      (used by Phase 47's UI).
- [ ] No domain-layer changes.
- [ ] No new top-level dependencies beyond `pyarrow` (already used by the
      synthetic engine's quality eval) and stdlib.
- [ ] All writers honor `output_filename` from the schema if set;
      otherwise default to `{schema.name}.{extension}`.
- [ ] Backend `pytest` suite passes; mypy / ruff clean on the new module.

## Ready-for-plan checklist

- [x] Vision articulated
- [x] Goals enumerated
- [x] Plan breakdown proposed (3 plans)
- [x] Approach options documented
- [x] Constraints listed
- [x] Risk areas explicitly called out for the highest-risk plan (44-02)
- [x] Dependencies declared
- [x] Open questions captured
- [x] Acceptance criteria defined
- [ ] Open Q #1 (EBCDIC library) confirmed
- [ ] Open Q #2 (decimal Arrow mapping) confirmed
- [ ] Open Q #3 (CSV BOM default) confirmed
- [ ] Open Q #4 (BDW scope) confirmed
- [ ] Open Q #5 (sync vs async) confirmed

Once the open questions are decided, ready for `/paul:plan` to generate
`44-01-PLAN.md`.

---
*Created: 2026-05-16 — Discuss phase output, feeds /paul:plan for Phase 44*
