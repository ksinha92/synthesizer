# Phase 51 Context — Generator Presets

> Discuss-phase output for v0.8.

## Vision

Replace the in-code generator vocabulary (currently a `GENERATOR_CHOICES`
constant in `database_view.py` and `DEFAULT_GENERATOR_BY_PII` in
`privacy_hub.py`) with a first-class `generator_presets` table users can
edit. Each preset is a named, reusable bundle: `generator_type`,
`config` JSONB, `consistency` flag. Masking rules can reference a preset.

## Goals

1. **Migration 017** — `generator_presets` table + nullable
   `masking_rules.preset_id` FK with ON DELETE SET NULL (deleting a preset
   keeps the rule but unlinks it).
2. **Model + repository** following the existing infrastructure pattern.
3. **CRUD endpoints** at `/api/v1/generator-presets` (project-agnostic;
   presets are global by default like Sensitivity Rules will be).
4. **Frontend page** at `/generator-presets` — table of presets with
   side drawer edit (matches the UX pattern from the reference design guide).
5. **Re-add Generator Presets link** to the GlobalNavBar (deferred from 48-01
   pending this route).

## Constraints

- Presets are **global** (no project_id). They're a vocabulary shared across
  the platform.
- `generator_type` must be one of the existing masking_type values
  (hash / redact / faker_replace / shuffle / nullify / fpe / passthrough).
- Backward compatible: rules without `preset_id` continue to work via their
  current `masking_type` column.
- Idempotent migration: the column add uses nullable, no default backfill.

## Plans

| Plan | Scope |
| --- | --- |
| **51-01** | Migration + model + repo + CRUD + page + nav link. Single plan. |

---
*Created: 2026-05-16*
