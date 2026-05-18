# Phase 45 Context — Sample File Parsing + Distribution Profiling

> Discuss-phase output for v0.7. Feeds `/paul:plan` for `45-01`.

## Vision

Round-trip the writers from Phase 44: build parsers that read CSV, fixed-width,
VSAM (EBCDIC decode + COMP-3 unpack + RDW handling), and Parquet/ORC back into
a `pandas.DataFrame`. Then profile each column (numeric distributions,
categorical frequencies, string patterns, null rates) and feed the profile
into `FakerEngine` so generated data matches the sample's shape.

## Goals

1. **Sample parsers** — one function per format, all returning a DataFrame
   keyed by `FileSchemaDefinition` field names. VSAM parsers reverse the COMP-3
   nibble math + EBCDIC overpunch + RDW framing established in 44-02.
2. **Distribution profiler** — produces a `ColumnProfile` per column with
   numeric stats (min/max/mean/std + distribution family hint), categorical
   value frequencies, regex pattern detection, and null rate.
3. **Profile-guided FakerEngine** — accept an optional `column_profiles` dict
   in `schema_metadata`; when present, sample from the learned distribution /
   frequencies / pattern instead of stock Faker.
4. **Round-trip unit tests** — write → parse → profile → generate, asserting
   structural similarity (column dtypes match, distributions overlap within tolerance).

## Constraints

- DDD: parsers + profiler live in `infrastructure/`; engine extension stays in
  `infrastructure/engine/`. No domain changes.
- No new top-level deps; stdlib + already-installed pandas/numpy/pyarrow.
- VSAM parser MUST round-trip files produced by 44-02 byte-for-byte.

## Plans

| Plan | Scope |
| --- | --- |
| **45-01** | Sample parsers (all 5 formats) + DistributionProfiler + FakerEngine `column_profiles` integration + tests |

(Originally split into 45-01 + 45-02; consolidated to one plan since the
parsers, profiler, and engine extension share fixtures and shipping them
together avoids inter-plan churn.)

## Acceptance (phase-level)

- Every writer in Phase 44 has a matching parser; round-trip CSV / fixed-width /
  VSAM (fixed + variable) / Parquet / ORC each pass byte-or-value assertions.
- `DistributionProfiler.profile_dataframe(df)` returns a dict mapping column
  name → `ColumnProfile`.
- `FakerEngine.generate(..., schema_metadata={"column_profiles": ...})`
  produces values bounded by the profile (min/max respected, null rate within
  ±10%, categorical values drawn from the learned set).

---
*Created: 2026-05-16*
