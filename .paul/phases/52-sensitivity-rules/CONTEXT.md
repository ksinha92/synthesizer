# Phase 52 Context — Sensitivity Rules Admin

> Discuss-phase output for v0.8.

## Vision

User-defined detectors that complement the built-in 4-layer PII pipeline.
A rule binds a *match strategy* (column-name regex, column-name substring,
or value regex) to a *suggested PII type* and optional *suggested generator
preset*. Rules are ordered by priority; the first match wins.

## Goals

1. **Migration 018** — `sensitivity_rules` table (name UNIQUE, description,
   match_type enum, pattern, suggested_pii_type, suggested_preset_id nullable
   FK to generator_presets, priority, enabled, timestamps).
2. **Model + CRUD endpoints** at `/api/v1/sensitivity-rules`.
3. **Frontend page** at `/sensitivity-rules` with a numbered table (priority
   visible) and a side drawer for create/edit.
4. **Sensitivity Rules link** added to GlobalNavBar (deferred from 48-01).
5. **Discovery integration** — wire `match_custom_rules()` as Layer 0 of the
   existing 4-layer PII pipeline so user rules win over built-in detectors
   when they match.

## Constraints

- `match_type` enum: `column_name_regex`, `column_name_contains`, `value_regex`.
- `suggested_preset_id` is nullable + `ON DELETE SET NULL` (deleting a preset
  doesn't kill the rule).
- Discovery integration is non-blocking: if rules table is empty, the existing
  4-layer pipeline runs unchanged.

## Plans

| Plan | Scope |
| --- | --- |
| **52-01** | Migration + model + CRUD + page + nav link + discovery integration. Single plan. |

---
*Created: 2026-05-16*
