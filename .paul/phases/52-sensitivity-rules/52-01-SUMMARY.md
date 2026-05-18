---
phase: 52-sensitivity-rules
plan: 01
subsystem: db, api, frontend
tags: [sensitivity-rules, migration, crud, side-drawer, nav]
requires:
  - phase: 48-shell-and-tokens
  - phase: 51-generator-presets
provides:
  - Migration 018 — sensitivity_rules table with priority/enabled/match_type/pattern + suggested_preset_id FK to generator_presets
  - SensitivityRuleModel
  - GET / POST / PUT / DELETE /api/v1/sensitivity-rules
  - /sensitivity-rules page (numbered table + side drawer)
  - Sensitivity Rules link re-added to GlobalNavBar
duration: ~25min
completed: 2026-05-16
---

# Phase 52 Plan 01: Sensitivity Rules Admin

**Live functional verification: POST + bad-regex 400 + DELETE round-trip all succeeded.**

## Highlights
- **Migration 018** adds `sensitivity_rules` (UNIQUE name, description,
  match_type, pattern, suggested_pii_type, nullable `suggested_preset_id` →
  `generator_presets.id` with `ON DELETE SET NULL`, priority indexed,
  enabled boolean, timestamps).
- **Backend CRUD** validates:
  - `match_type` ∈ {`column_name_regex`, `column_name_contains`, `value_regex`}
  - `suggested_pii_type` ∈ 11-value PIIType set
  - regex patterns compile (via `re.compile` pre-flight) — bad regex → 400 with the actual `re.error` message
  - UNIQUE name violations → 409
- **Frontend page** at `/sensitivity-rules`:
  - Numbered table showing priority order + Name, Match, Pattern (truncated),
    Suggested PII, Preset name (resolved by joining with `/generator-presets`),
    Enabled pill, Edit/Delete.
  - Side drawer with all fields including a preset dropdown populated from
    the live presets list (lets rules suggest a preset by name).
  - Pattern placeholder switches between regex-style hint and substring hint
    based on the selected match type.
- **Nav**: `Sensitivity Rules` link re-added to `GlobalNavBar` next to
  Generator Presets (deferred from 48-01 pending this route).

## API contract
```
GET    /api/v1/sensitivity-rules        list ordered by (priority, name)
POST   /api/v1/sensitivity-rules        { name, match_type, pattern, suggested_pii_type, ... }
GET    /api/v1/sensitivity-rules/{id}
PUT    /api/v1/sensitivity-rules/{id}   partial update
DELETE /api/v1/sensitivity-rules/{id}   → 204
```

## Discovery-pipeline integration — deferred

Per the phase context, the original goal also called for wiring custom rules
into the 4-layer PII pipeline at `infrastructure/ai/pii_detector.py`. That
hook is intentionally **deferred** because:

1. `PIIDetector.detect()` is not DB-aware today — adding a query inside
   would change its responsibility surface. The right move is to load rules
   once in the discovery Celery task and pass them in.
2. The user-facing admin surface (this plan) ships independently and is
   immediately useful for capturing organization-specific detectors.
3. Phase 53 already touches the detector area for recommended generators —
   the rules wire-up will land alongside that work to keep the touch
   surgical.

**Follow-up scope:** in 53-01 or a small 52-02:
- Add `match_custom_rules(column_name, sample_text, rules)` helper in a new
  module (pure function, no I/O).
- In `discovery_tasks._run_discovery_async`, load all `enabled=True` rules
  once before the detector loop and pass them through schema_metadata.
- Add Layer 0 in `PIIDetector.detect()` that calls the helper; first match
  wins, short-circuits subsequent layers.

## Functional smoke test (executed at apply time)
- POST a `column_name_contains` rule (`acct` → `financial_account`, priority 50) → 201 with full body.
- POST a `column_name_regex` rule with `[unclosed` → 400 `{"error":"invalid_regex"}` with the actual Python `re.error` message inline.
- DELETE the test rule → 204.

## Manual verification
- [ ] Visit `/sensitivity-rules` — page renders inside the new shell.
- [ ] Click New Rule, fill all fields including a preset, save; row appears with right priority order.
- [ ] Edit the rule; values persist.
- [ ] Bad regex pattern in the form → save fails with toast "check pattern is valid regex".
- [ ] Sensitivity Rules link visible in the dark global nav, between Generator Presets and Admin.

---
*Phase: 52-sensitivity-rules, Plan: 01 — Completed 2026-05-16*
