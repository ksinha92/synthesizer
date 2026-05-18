# DataWrangler v0.8 — UX Refactor

**Shipped: 2026-05-16**

Eight-phase refactor reshaping the app chrome and adding the working surfaces
expected of an enterprise TDM tool. No previously-shipped capability was
removed; the AI assistant, compliance reports, workflow DAG, file-based
synthetic, RBAC / audit / webhooks / DLQ, CLI, onboarding, and notification
center are all reachable in the new IA.

## What's new

### Chrome — Phase 48

Two-bar app shell replaces the sidebar:

- **Dark global nav** with brand, Projects, Generator Presets, Sensitivity
  Rules, Admin, ⌘K search, theme toggle, notifications, AI assistant, user
  menu.
- **Workspace tab bar** on project routes: Privacy Hub · Database View ·
  Connections · Discovery · Masking · Synthetic · Subsetting · Workflows ·
  Jobs · Compliance.
- Right-pinned **Generate Data ▾** split-button covering Run Discovery /
  Generate Synthetic / Apply Masking / Run Subset / Execute Workflow.
- Design tokens (`--dw-*`) added to `globals.css` for the new palette,
  status pill colors, and CTA gradient.

Default theme behavior: System default for content; global bar always dark.

### Privacy Hub — Phase 49

New goal-driven project landing page at `/projects/[id]`:

- Three counters — Sensitive columns, Protected, Unprotected.
- Recommended Generators table grouped by PII type with per-row Apply and a
  hero "Apply all" button.
- Activity feed below.

Backend: `GET /privacy-hub` aggregator + `POST /privacy-hub/apply-all`
(idempotent bulk masking-rule creation; auto-creates a "Default" policy).

### Unified Database View — Phase 50

Single working surface at `/projects/[id]/database`:

- 220px schema-table tree on the left with per-table column counts.
- Filterable column table with status pills (Protected / Unprotected / Not
  sensitive) and inline generator dropdown.
- Per-row dropdown calls `POST /database/columns/{id}/rule` to upsert or
  `DELETE` to clear the rule.

### Generator Presets — Phase 51

Reusable, named generator configurations at `/generator-presets`:

- Table with Name, Generator, Consistency pill, Occurrences (per-rule count),
  Edit/Delete.
- Side drawer for create/edit including a JSON config textarea (validated
  before submit).
- Migration 017 adds `generator_presets` table + nullable
  `masking_rules.preset_id` FK (`ON DELETE SET NULL` — preset delete keeps
  rules and unlinks).

### Sensitivity Rules — Phase 52

User-defined detectors at `/sensitivity-rules`:

- Numbered table in priority order: Name, Match type, Pattern, Suggested
  PII, Preset (joined from `/generator-presets`), Enabled.
- Side drawer with match-type-aware pattern hints.
- Three match strategies: `column_name_contains`, `column_name_regex`,
  `value_regex`. Regex compiled at API time — bad patterns return 400
  with the real `re.error` message.
- Migration 018 adds `sensitivity_rules` table + nullable
  `suggested_preset_id` FK to `generator_presets`.

### Custom-rule integration into discovery — Phase 53

User rules wire into the existing 4-layer PII detection pipeline:

- Discovery service runs `match_all_rules(column_name, raw_samples, rules)`
  in user-defined priority order **before** sample masking. First match
  across both column-name and value-regex strategies wins.
- A match stamps `column.pii_type` + `pii_confidence(detector="custom_rule")`
  + `classification=AUTO_CLASSIFIED`.
- Detector honors upstream stamps (`detector.startswith("custom_rule")`) by
  skipping Layers 1–4 entirely so `_combine_scores` can't overwrite the hit.
- Detector also has a fallback Layer 0 for column-name rules when discovery
  hasn't pre-classified the column.

Linked-column schema lands with migration 019:

- `masking_rules.linked_column_ids` (`UUID[]`) and `consistency_group`
  (indexed text) for future joint-generation work.

### Destinations + virtual FKs + schema diff — Phase 54

- Migration 020 adds `output_mode` to `synthetic_configs` and `subset_configs`
  (allowed values: `same_database` / `different_connection` / `download_zip` /
  `s3`) and `is_virtual` to `discovered_relationships`.
- `POST /projects/{id}/relationships` creates a user-asserted virtual FK.
- `DELETE /projects/{id}/relationships/{id}` removes any relationship.
- `GET /projects/{id}/discovery/diff?connection_id=...` runs a read-only
  live introspection and returns the structural delta vs. persisted state
  (added / removed / changed tables and columns).

## Tonic-brand scrub

The reference UX was modeled on Tonic Structural during planning. All
identifiers, CSS variables, file names, and references to "Tonic" were
removed from source code, docs, and PAUL artifacts before milestone close.
CSS tokens use the `--dw-*` namespace.

## Migrations applied in v0.8

| Rev | Adds |
| --- | --- |
| 017 | `generator_presets` table + `masking_rules.preset_id` FK (SET NULL) |
| 018 | `sensitivity_rules` table |
| 019 | `masking_rules.linked_column_ids` + `consistency_group` |
| 020 | `synthetic_configs.output_mode` + `subset_configs.output_mode` + `discovered_relationships.is_virtual` |

## New endpoints

| Method | Path |
| --- | --- |
| GET | `/api/v1/projects/{id}/privacy-hub` |
| POST | `/api/v1/projects/{id}/privacy-hub/apply-all` |
| GET | `/api/v1/projects/{id}/database` |
| POST/DELETE | `/api/v1/projects/{id}/database/columns/{column_id}/rule` |
| GET / POST / PUT / DELETE | `/api/v1/generator-presets` (+ `/{id}`) |
| GET / POST / PUT / DELETE | `/api/v1/sensitivity-rules` (+ `/{id}`) |
| GET | `/api/v1/projects/{id}/discovery/diff?connection_id=...` |
| POST | `/api/v1/projects/{id}/relationships` |
| DELETE | `/api/v1/projects/{id}/relationships/{relationship_id}` |

## Quality gate (this release)

- Backend unit tests: **148 / 148 passing**.
- Frontend `tsc --noEmit`: **clean**.
- `ruff check app/`: 39 auto-fixed; 40 remaining are pre-existing
  intentional patterns (`from X import *` in module __init__s, SQLAlchemy
  `== True` filter literals, lazy module-level imports). No new lint
  issues introduced this milestone.
- Alembic head: **020**.

## Known deferred work

- **Masking engine joint-generation** for `linked_column_ids` /
  `consistency_group` — schema lands in 019; engine update queued for a
  future plan.
- **UI surfacing** of `output_mode`, virtual-FK add/remove on the
  relationships graph, and a "Schema changes" panel. APIs exist; UI lives
  in the next milestone.
- **Generator Presets ↔ Database View binding** — Database View currently
  reads the in-code generator list. Wiring it to the presets table is a
  small follow-up.
