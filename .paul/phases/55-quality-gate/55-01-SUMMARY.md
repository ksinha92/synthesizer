---
phase: 55-quality-gate
plan: 01
subsystem: docs, lint, ci
tags: [quality-gate, milestone-close, release-notes, ruff, tsc]
requires:
  - phase: 48-shell-and-tokens
  - phase: 49-privacy-hub
  - phase: 50-database-view
  - phase: 51-generator-presets
  - phase: 52-sensitivity-rules
  - phase: 53-recommended-and-linked
  - phase: 54-destinations-vfk-diff
provides:
  - docs/RELEASE-NOTES-v0.8.md
  - 39 ruff auto-fixes across the backend (mostly unused imports)
  - v0.8 milestone close (ROADMAP + STATE updated)
duration: ~15min
completed: 2026-05-16
---

# Phase 55 Plan 01: Quality Gate + v0.8 Ship

## Quality-gate sweep

| Check | Result |
| --- | --- |
| Backend `pytest tests/ --ignore=tests/integration` | **148 / 148 passing** |
| Frontend `npx tsc --noEmit -p .` | **clean** (no output) |
| Backend `ruff check app/` | 39 auto-fixed; 40 remaining (categorized below) |
| Alembic head | **020** |
| Tonic-brand scrub | **0** identifier hits in source / docs / PAUL artifacts (excl. Python `time.monotonic()` substring) |

## Ruff residual after auto-fix

| Rule | Count | Category |
| --- | --- | --- |
| F405 | 19 | Module-level `from X import *` in `__init__.py` files (pre-existing pattern) |
| F841 | 9 | Local var assigned but not used — some in loops, some intentional placeholders |
| F403 | 5 | The `from X import *` themselves; same files as F405 |
| E402 | 4 | Module-level imports not at top — intentional lazy imports inside functions/branches |
| E712 | 3 | `MaskingRuleModel.column_id == True` / `enabled == True` — required SQLAlchemy filter syntax; `is True` doesn't work in a WHERE clause |

None of these are new in v0.8; all reflect existing project conventions or
SQLAlchemy idioms. Documented here so a future cleanup plan has a clear
target rather than treating each as a new regression.

## Files modified in this plan

- Backend: 39 files touched by `ruff --fix` (unused imports removed).
- `docs/RELEASE-NOTES-v0.8.md` — new.
- `.paul/STATE.md`, `.paul/ROADMAP.md` — milestone close.

## v0.8 milestone summary

8 phases, 8 plans, 4 migrations (017–020), ~12 new endpoints, 5 new pages /
routes, full source-code scrub of the planning-time competitor brand name.
148 / 148 backend unit tests passing; frontend tsc clean throughout.

Deferred work captured in the release notes:
- Masking-engine joint generation honoring `linked_column_ids`.
- UI surfacing of `output_mode`, virtual-FK toggling on the relationships
  graph, and a "Schema changes" panel on connection detail.
- Generator-presets → Database View binding (replace in-code generator list
  with preset references).

## Manual verification checklist for v0.8 close-out

- [ ] Navigate the new TopShell: global nav links work, workspace tabs work,
      Generate Data ▾ split-button opens, Cmd-K opens the command palette,
      theme toggle switches content theme but keeps the global bar dark.
- [ ] Project landing page shows the Privacy Hub trio of counters + the
      Recommended Generators table.
- [ ] Database View page renders with schema tree + filterable column table;
      inline generator dropdown creates/clears rules.
- [ ] `/generator-presets` page: create + edit + delete round-trip in the UI.
- [ ] `/sensitivity-rules` page: same round-trip; bad regex shows the error
      toast.
- [ ] On a real project: create a sensitivity rule with `column_name_contains`
      → re-run discovery → discover the rule's PII type stamped on matching
      columns at confidence 0.9.

---
*Phase: 55-quality-gate, Plan: 01 — Completed 2026-05-16*
