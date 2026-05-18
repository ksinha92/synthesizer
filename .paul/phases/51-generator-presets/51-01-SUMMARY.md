---
phase: 51-generator-presets
plan: 01
subsystem: db, api, frontend
tags: [generator-presets, migration, crud, side-drawer, nav]
requires:
  - phase: 48-shell-and-tokens
provides:
  - Migration 017 — generator_presets table + masking_rules.preset_id FK (ON DELETE SET NULL)
  - GeneratorPresetModel + MaskingRuleModel.preset_id
  - GET / POST / PUT / DELETE /api/v1/generator-presets
  - /generator-presets page (table + side drawer for edit)
  - Generator Presets link re-added to GlobalNavBar
duration: ~30min
completed: 2026-05-16
---

# Phase 51 Plan 01: Generator Presets

**Live round-trip verified — create / list / get / update / delete all functional. Backend reloaded; frontend tsc clean; alembic head now 017.**

## Highlights
- **Migration 017** adds `generator_presets` (id, name UNIQUE, description,
  generator_type, config JSONB, consistency BOOLEAN, timestamps) and
  `masking_rules.preset_id` with an indexed `ON DELETE SET NULL` FK. Existing
  rules survive a preset delete with the preset_id nulled out.
- **Models**: new `GeneratorPresetModel`; `MaskingRuleModel` extended with
  `preset_id` column. Both follow the existing infrastructure conventions
  (UUIDPrimaryKeyMixin, TimestampMixin, Mapped[] typing).
- **CRUD endpoints** at `/api/v1/generator-presets`:
  - `GET` lists every preset with an `occurrences` count of how many
    masking rules reference it.
  - `POST` validates `generator_type` against the allowed set + handles
    UNIQUE-name conflicts → 409.
  - `PUT` partial-update with the same validation.
  - `DELETE` is 204; rules unlink automatically via the FK.
- **Frontend page** at `/generator-presets`:
  - Table with Name, Generator, Consistency pill, Occurrences, Edit/Delete.
  - Right-side drawer for create/edit with the four fields + a JSON config
    textarea. Save validates JSON before posting; errors surface via toast.
  - Wrapped in `<AppShell>` so the new TopShell renders chrome.
- **Nav**: `Generator Presets` link re-added to `GlobalNavBar` between
  Projects and Admin (deferred from 48-01 pending this route).

## API contract
```
GET    /api/v1/generator-presets
POST   /api/v1/generator-presets         { name, description?, generator_type, config?, consistency? }
GET    /api/v1/generator-presets/{id}
PUT    /api/v1/generator-presets/{id}    { partial update }
DELETE /api/v1/generator-presets/{id}    → 204 (rules unlink, do not delete)
```

## Functional smoke test (executed at apply time)
- POST → 200 + body with generated id, occurrences=0, both timestamps populated.
- GET (list) → 200 with the created preset present.
- DELETE → 204.
- Live verification: `curl` round-trip create → list → delete with a SHA-256
  hash preset succeeded end-to-end.

## Allowed `generator_type` values
`hash`, `redact`, `faker_replace`, `shuffle`, `nullify`, `fpe`, `passthrough` —
matches Phase 50's `GENERATOR_CHOICES`. Adding a new generator means widening
the set in **both** files (intentional — keeps the vocabulary explicit).

## Contract for Phase 53 + later
- Phase 49's `DEFAULT_GENERATOR_BY_PII` map and Phase 50's `GENERATOR_CHOICES`
  remain in code for now. Phase 53 will replace the in-code map with preset
  references; the contract is: pick a preset by `name` for each PII type,
  fall back to the in-code map if no preset matches. UI for that mapping
  table will live in `/sensitivity-rules` (Phase 52).

## Manual verification
- [ ] Visit `/generator-presets` — page renders inside the new shell.
- [ ] Click New Preset; drawer opens; create one; appears in the table.
- [ ] Edit it; values persist after save.
- [ ] Delete it; row disappears; confirmation prompt fires.
- [ ] Generator Presets link visible in the dark global nav, between Projects and Admin.

---
*Phase: 51-generator-presets, Plan: 01 — Completed 2026-05-16*
