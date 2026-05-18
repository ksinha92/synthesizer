---
phase: 45-sample-profiling
plan: 01
subsystem: infrastructure
tags: [parsers, profiler, faker, round-trip, sample-files]
requires:
  - phase: 44-file-writers
provides:
  - sample_file_parser module (parse_csv, parse_fixed_width, parse_vsam, parse_columnar, parse dispatcher)
  - DistributionProfiler + ColumnProfile dataclass
  - FakerEngine extension consuming schema_metadata["column_profiles"]
  - 19 unit tests
affects: [46-orchestration, 47-frontend]
duration: ~20min
completed: 2026-05-16
---

# Phase 45 Plan 01: Sample Parsers + Profiler + Profile-Guided FakerEngine

**142/142 backend unit tests green (+19 from this plan).**

## Highlights
- **Parsers** reverse every Phase 44 writer with byte/value-exact round-trip:
  CSV (via `csv.DictReader`), Fixed-width (with implied-decimal scaling), VSAM
  (EBCDIC decode + COMP-3 nibble unpack + display-overpunch reverse + RDW
  framing), Parquet + ORC (pyarrow).
- **DistributionProfiler** classifies each column as numeric / categorical /
  string / empty; numeric profiles carry min/max/mean/std; categorical
  profiles carry frequencies (cardinality < 50); string profiles attempt a
  digit/letter pattern hint; all carry null_rate + sample_values.
- **FakerEngine** consults `schema_metadata["column_profiles"]` when present:
  numeric profiles constrain to [min, max], categorical profiles sample
  weighted by frequencies, null_rate replaces the hard-coded 10% draw. PII
  flag still wins to prevent profile-driven leakage.

## Contract for downstream
- Phase 46 orchestrator can use `sample_file_parser.parse(path, schema)` to
  ingest sample files for FK pool building or profile training.
- Phase 47 file-output UI can call `DistributionProfiler.profile_dataframe(df)`
  on uploaded samples and ship the result alongside the FileSchema into
  generation requests.

---
*Phase: 45-sample-profiling, Plan: 01 — Completed 2026-05-16*
