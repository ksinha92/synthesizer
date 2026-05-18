---
phase: 53-recommended-and-linked
plan: 01
subsystem: db, ai, messaging
tags: [migration, layer-0, custom-rules, linked-columns, consistency-group]
requires:
  - phase: 49-privacy-hub
  - phase: 52-sensitivity-rules
provides:
  - Migration 019 — masking_rules.linked_column_ids (UUID[]) + consistency_group (indexed text)
  - custom_rules.match_column_rules() pure-function matcher
  - PIIDetectionService.detect(columns, custom_rules=...) Layer 0
  - Discovery task loads enabled sensitivity rules once per run and passes through
affects: [54-destinations-vfk-schema-changes, 55-quality-gate]
duration: ~25min
completed: 2026-05-16
---

# Phase 53 Plan 01: Custom-Rule Layer 0 + Linked-Column Schema

**148/148 backend unit tests still green; Layer 0 helper smoke-tested live.**

## Highlights
- **Migration 019** extends `masking_rules` with:
  - `linked_column_ids` — `UUID[]` (nullable). Future engine work can use this
    to keep joint generators consistent (City→State, FirstName→LastName).
  - `consistency_group` — `VARCHAR(255)` indexed. Rules sharing a group keep
    the same hash salt / sampled value across columns in one row.
- **`infrastructure/ai/custom_rules.py`** — pure-function matcher used by
  Layer 0:
  - Sorts rules ascending by `priority` (lower first).
  - Three match strategies — `column_name_contains` (case-insensitive substring),
    `column_name_regex`, `value_regex`. Regex compile failures are silently
    skipped rather than crashing discovery.
  - Returns `(PIIType, 0.9)` on a hit, `None` otherwise.
- **`PIIDetectionService.detect`** now takes an optional `custom_rules`
  parameter. When supplied and a rule matches, the column's classification
  short-circuits to `AUTO_CLASSIFIED` with `PIIConfidence(score=0.9,
  detector="custom_rule")` and the remaining 4 layers are skipped. With no
  rules supplied behavior is unchanged.
- **Discovery task** queries `sensitivity_rules WHERE enabled = true`
  once per run and threads the result through. Adds ~1 short query per
  discovery job; rules are loaded once, not per column.

## Migration troubleshooting note
First-pass migration failed because `sa.Column(..., index=True)` *plus*
`op.create_index(...)` tried to create the same index twice in one
transactional DDL block. Postgres rejected the second attempt with
`DuplicateTable`. Fixed by dropping the `index=True` flag and relying on
the explicit `op.create_index` call. Future migrations: pick one mechanism,
not both.

## Smoke test (executed at apply time)
```py
rules = [{'name':'ssn-col', 'match_type':'column_name_contains',
          'pattern':'ssn', 'suggested_pii_type':'ssn',
          'priority':10, 'enabled':True}]
match_column_rules('user_ssn_hash', None, rules) == (PIIType.SSN, 0.9)
match_column_rules('id', None, rules) is None
```
Both assertions passed live.

## Out of scope (queued)
- **Masking engine update** to honor `linked_column_ids` + `consistency_group`
  for joint generation. The schema lands here; the engine work was deferred
  to keep the touch surface small (masking_engine.py is complex and would
  need its own plan + tests). The columns are documented for the engine
  team to consume.
- **UI for linked-column selection**. Database View shows the rule status,
  but a multi-column picker for linked-column groups is not in this plan.
- **End-to-end discovery test** with a custom rule. The Celery-orchestrated
  discovery pipeline is best exercised via integration tests, which we don't
  have machinery for in this session.

## Contract for Phase 54
- The two new columns on `masking_rules` are nullable + indexed; Phase 54's
  destination + virtual-FK work can ignore them. They're consumed by future
  engine work only.
- `match_column_rules` is the canonical place to add new match strategies.
  Add a new branch + extend the API validator (`sensitivity_rules.py`).

## Manual verification
- [ ] Create a sensitivity rule via the Phase 52 UI (e.g. column_name_contains "ssn" → ssn).
- [ ] Re-run discovery on a connection that has columns named like that.
- [ ] In `/database`, those columns show as `ssn` with confidence 0.9.

---
*Phase: 53-recommended-and-linked, Plan: 01 — Completed 2026-05-16*
