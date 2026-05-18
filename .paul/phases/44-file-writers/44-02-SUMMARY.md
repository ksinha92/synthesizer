---
phase: 44-file-writers
plan: 02
subsystem: infrastructure
tags: [vsam, ebcdic, comp-3, comp, overpunch, rdw, mainframe]

requires:
  - phase: 44-file-writers
    plan: 01
    provides: BaseFileWriter, write_atomic

provides:
  - ebcdic_codec module (stdlib cp037/cp1140 wrapper with space/zero helpers)
  - cobol_encoding module (encode_comp3, encode_comp, encode_display_signed)
  - VSAMWriter (VSAM_FIXED and VSAM_VARIABLE)
  - 33 unit tests (18 cobol_encoding + 15 vsam_writer)

affects: [44-03-columnar-registry, 45-sample-profiling, 46-orchestration]

tech-stack:
  added: []
  patterns:
    - "Pure-function COBOL encoders separated from writer for unit-testability"
    - "Big-endian RDW = (record_length + 4).to_bytes(2,'big') + b'\\x00\\x00'"
    - "COMP-3 nibble count = digits + 1; bytes = ceil((digits+1)/2); leading-pad nibble when odd"
    - "Overpunch maps EBCDIC last-digit byte to digit+sign (+0..9 = '{','A'..'I'; -0..9 = '}','J'..'R')"

key-files:
  created:
    - backend/app/infrastructure/writers/ebcdic_codec.py
    - backend/app/infrastructure/writers/cobol_encoding.py
    - backend/app/infrastructure/writers/vsam_writer.py
    - backend/tests/unit/test_cobol_encoding.py
    - backend/tests/unit/test_vsam_writer.py

key-decisions:
  - "Encoders are pure functions in a separate module — VSAMWriter only orchestrates."
  - "stdlib codecs cp037 + cp1140 cover Ameritas use cases; no third-party `ebcdic` package."
  - "VSAMWriter implicitly defaults schema.metadata['implied_decimal'] to True since COBOL has no other convention."
  - "RDW length includes itself (record_length + 4), not the payload alone."

patterns-established:
  - "Golden-byte fixtures > parsed-value equality — only way to catch off-by-one nibble bugs"
  - "Validator runs format + encoding compatibility checks before any rendering"

duration: ~25min
completed: 2026-05-16
---

# Phase 44 Plan 02: VSAMWriter Summary

**EBCDIC code-page codec, COBOL COMP / COMP-3 / overpunch encoders, and the
VSAMWriter subclass covering both fixed and variable record formats.
Golden-byte fixtures lock the wire format.**

## Performance

| Metric | Value |
|--------|-------|
| Duration | ~25min |
| Completed | 2026-05-16 |
| Tasks | 5 of 5 |
| Files created | 5 |
| Unit tests added | 33 (18 cobol_encoding + 15 vsam_writer) |
| Full suite | 108/108 passing |

## Acceptance Criteria Results

| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1: EBCDIC codec (cp037/cp1140) | Pass | Stdlib only; ValueError on unknown encoding |
| AC-2: COMP-3 packed-decimal golden bytes | Pass | All 9 fixtures byte-exact |
| AC-3: COMP big-endian two's complement | Pass | Range + sign + byte-width tests pass |
| AC-4: Display-signed overpunch | Pass | Both +0..9 and -0..9 overpunch chars in EBCDIC |
| AC-5: VSAM fixed — no terminator | Pass | File size = N × record_length |
| AC-6: VSAM variable RDW prefix | Pass | 4-byte big-endian header including self |
| AC-7: Mixed-type record rendering | Pass | All branches in _render_field exercised |
| AC-8: Golden fixtures across types/pages/formats | Pass | 13 record-level tests |

## Deviations from Plan

| Type | Count | Impact |
|------|-------|--------|
| Plan-doc errata | 2 | Two golden values in the PLAN file were arithmetically wrong; corrected during verify |
| Code deviations | 0 | — |

**Errata corrected:**
1. AC-2 listed `encode_comp3(9950, 9, True) == b"\\x00\\x00\\x00\\x09\\x95\\x0c"` (6 bytes). Correct is 5 bytes: `b"\\x00\\x00\\x09\\x95\\x0c"` (9 digits + sign = 10 nibbles even = 5 bytes).
2. AC-2 listed `encode_comp3(99999, 5, False) == b"\\x09\\x99\\x9f"`. Correct is `b"\\x99\\x99\\x9f"` (5 digits + sign = 6 nibbles even, no leading pad).

Tests in `test_cobol_encoding.py` carry the corrected values; the implementation
matched the math throughout.

## Contract for downstream plans

44-03 (registry) will pick up `VSAMWriter` via `supported_formats()` →
`{VSAM_FIXED, VSAM_VARIABLE}`. No further changes needed in this module.

## Next Phase Readiness

**Plan 44-02 complete. Ready for Plan 44-03 (ColumnarWriter + Writer Registry).**

---
*Phase: 44-file-writers, Plan: 02*
*Completed: 2026-05-16*
