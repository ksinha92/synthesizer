# Enterprise Plan Audit Report

**Plan:** .paul/phases/43-schema-parsers-internal-model/43-01-PLAN.md
**Audited:** 2026-04-03
**Verdict:** Conditionally Acceptable — now acceptable after applied fixes

---

## 1. Executive Verdict

**Conditionally acceptable**, upgraded to **acceptable** after 4 must-have and 3 strongly-recommended fixes applied.

The plan's architecture is sound — clean DDD separation, zero framework deps in domain, sensible domain modeling for file schemas. However, the original plan had gaps that would cause real problems: no input size limits (DoS vector), ambiguous COMP-3 byte length formula (data corruption risk), no serialization contract (fragile persistence coupling in 43-02), and underspecified validation rules (silent bad state propagation).

I would sign off on this plan as-is with the applied fixes. The remaining deferred items are genuine "can wait" — they improve robustness but don't block correctness.

## 2. What Is Solid (Do Not Change)

- **DDD boundary discipline.** Domain model in `domain/synthetic/`, parser in `infrastructure/parsers/`. Parser depends on domain, not the reverse. This is correctly layered and will prevent coupling problems as more parsers are added.

- **Comprehensive PIC clause coverage.** The plan covers PIC X, PIC 9, PIC S9, V (implied decimal), COMP, COMP-3, REDEFINES, OCCURS, FILLER, level 88 skip. This handles the vast majority of real-world COBOL copybooks.

- **Explicit REDEFINES position handling.** "Reuse the start_position of the redefined field, do NOT advance offset" — this is the correct behavior and a common source of bugs in copybook parsers. Good that it's called out explicitly.

- **Boundaries section.** Clear protection of existing entities, services, and repository. Explicitly scoping out API endpoints and persistence (deferred to 43-02). This prevents scope creep.

- **FileSetDefinition with cross-file FK.** Modeling FK relationships at the schema level (not just at generation time) enables topological validation before generation begins — fail fast.

## 3. Enterprise Gaps Identified

### 3.1 Input Size Limits (DoS Prevention)
The copybook parser accepts arbitrary string input with no size guard. A malicious or accidental multi-MB copybook with deeply nested OCCURS could consume unbounded memory during expansion. In a web-facing API (43-02 exposes this), this is a straightforward DoS vector.

### 3.2 COMP-3 Byte Length Formula Ambiguity
AC-3 stated `(n+1)//2 + sign` which is ambiguous. The standard COMP-3 encoding is: each digit = 1 nibble, sign = 1 nibble, packed into bytes. The correct formula is `ceil((total_digits + 1) / 2)` where +1 accounts for the sign nibble. The original formula could be misinterpreted as adding a full byte for sign, producing wrong byte lengths (and thus wrong record lengths, corrupt VSAM files).

### 3.3 Missing Serialization Contract
FileSchemaDefinition and FileFieldDefinition are pure dataclasses with no `to_dict()`/`from_dict()`. Plan 43-02 needs to persist these as JSONB. Without a serialization contract in the domain layer, the persistence layer must implement ad-hoc serialization, which creates fragile coupling and risks data loss on enum types (CompType, FileFormat, EncodingType).

### 3.4 Underspecified validate() Method
The plan mentions `validate() -> list[str]` with "check for position overlaps, missing lengths, etc." — the "etc." is a red flag. Validation rules must be enumerated, otherwise implementers will miss checks and bad schemas will propagate to file writers, producing corrupt output.

### 3.5 Mutable Value Objects
FileFieldDefinition represents a value object (immutable by DDD convention). Using a regular dataclass allows mutation after construction, which can cause subtle bugs when the same field definition is shared across multiple schemas.

### 3.6 Nested OCCURS Not Addressed
COBOL allows OCCURS within OCCURS (e.g., a table within a table). The plan says "expand to repeated field groups" but doesn't specify behavior for nested OCCURS. If unsupported, it should explicitly reject with a clear error rather than silently producing wrong output.

### 3.7 Error Messages Without Line Context
"Raise ValueError with descriptive message" is insufficient for debugging. When a user uploads a 500-line copybook and gets "Invalid PIC clause", they have no idea where to look. Line numbers in error messages are not optional for a parser.

## 4. Upgrades Applied to Plan

### Must-Have (Release-Blocking)

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| 1 | Input size limits for DoS prevention | Task 2 action (step a0), AC-5 added | Added 1MB / 10K line guard before parsing begins |
| 2 | COMP-3 byte length formula clarification | AC-3, Task 2 action (PIC clause section) | Replaced ambiguous `(n+1)//2 + sign` with `ceil((total_digits + 1) / 2)` with worked examples |
| 3 | Serialization contract (to_dict/from_dict) | Task 1 action (FileFieldDefinition, FileSchemaDefinition), AC-6 added | Added to_dict()/from_dict() methods to both classes for JSON-safe round-tripping |
| 4 | validate() rules enumerated | Task 1 action (FileSchemaDefinition) | Specified 5 concrete validation checks: position overlaps, byte_length <= 0, duplicate names, record_length consistency, format/encoding compatibility warning |

### Strongly Recommended

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| 5 | Frozen dataclasses for value objects | Task 1 action (FileFieldDefinition, CrossFileFK) | Changed to frozen dataclass for domain immutability safety |
| 6 | Nested OCCURS explicit rejection | Task 2 action (OCCURS section), AC-3, AC-5 | Added ValueError with line number when nested OCCURS detected |
| 7 | Error messages with line numbers | Task 2 error handling section | Specified line number + offending clause text in all ValueError messages; warnings include line numbers |

### Deferred (Can Safely Defer)

| # | Finding | Rationale for Deferral |
|---|---------|----------------------|
| 1 | VSAM max record length validation (32,760 bytes for KSDS, 32,761 for ESDS) | Small volume use case per user requirements; writers (Phase 44) can enforce format-specific limits closer to output |
| 2 | PIC editing symbols (Z, *, $, comma, period) | These are display-format PIC clauses rarely used in data records (more common in reports). Can add support as needed. Parser should log a warning for unrecognized PIC symbols. |
| 3 | COBOL COPY/REPLACE statement support | These are preprocessor directives. Real copybooks are usually pre-expanded before upload. Can add in a future iteration if needed. |

## 5. Audit & Compliance Readiness

**Defensible audit evidence:** The plan produces pure domain objects with validation methods. Combined with the serialization contract (to_dict), all schema definitions can be persisted and reconstructed for post-incident analysis.

**Silent failure prevention:** The added validate() specification with 5 concrete checks ensures bad schemas are caught at creation time, not at file write time. The input size guard prevents resource exhaustion. Line-numbered errors enable actionable debugging.

**Post-incident reconstruction:** to_dict() serialization means every schema that enters the system can be logged and reproduced. The metadata dict (storing source copybook name, warnings) provides provenance.

**Ownership:** Clear — domain model owned by the synthetic bounded context, parser owned by infrastructure/parsers. No cross-cutting concerns.

## 6. Final Release Bar

**What must be true before this plan ships:**
- COMP-3 byte length calculation is mathematically correct and verified with multiple test cases (S9(7)V99, 9(5), S9(3), S9(15)V99)
- to_dict()/from_dict() round-trip cleanly for all enum types
- validate() catches all 5 specified conditions
- Oversized input is rejected before parsing begins
- All parse errors include line numbers

**Remaining risks if shipped as-is (with fixes applied):**
- PIC editing symbols (Z, *, $) will raise ValueError rather than being handled gracefully. Acceptable for v0.7 since these are uncommon in data copybooks.
- COPY/REPLACE preprocessor directives are unsupported. Users must upload pre-expanded copybooks. Acceptable with documentation.

**Sign-off:** With the 7 applied fixes, I would sign my name to this plan. The domain model is clean, the parser is well-scoped, and the safety boundaries are adequate for the stated use case (small volume, internal tool).

---

**Summary:** Applied 4 must-have + 3 strongly-recommended upgrades. Deferred 3 items.
**Plan status:** Updated and ready for APPLY

---
*Audit performed by PAUL Enterprise Audit Workflow*
*Audit template version: 1.0*
