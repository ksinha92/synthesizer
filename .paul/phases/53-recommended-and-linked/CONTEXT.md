# Phase 53 Context — Custom Rule Integration + Linked-Column Schema

> Discuss-phase output for v0.8.

## Vision

Two threads:
1. **Wire Phase 52's `sensitivity_rules`** into the PII detection pipeline.
   When discovery runs, enabled rules are evaluated as a Layer 0 ahead of
   the four existing layers; the first column-name match wins with high
   confidence.
2. **Linked-column schema**. Add `linked_column_ids UUID[]` and
   `consistency_group TEXT` to `masking_rules`. The data structure lets
   future engine work generate City→State consistently. Engine update
   itself is deferred — this plan ships the schema + API surface.

Recommended-generators bulk apply already shipped in Phase 49.

## Goals

1. **Migration 019** — extend `masking_rules` with two nullable columns.
2. **Custom-rules helper** — pure function in `infrastructure/ai/custom_rules.py`
   matching a column against a list of enabled rule dicts.
3. **PIIDetectionService Layer 0** — accept a list of custom rule dicts and
   evaluate before Layer 1. Backward compatible (no rules → existing behavior).
4. **Discovery task wires rules** — load all enabled rules from DB once
   before invoking `detect()`.
5. **Masking-rule API extension** — `linked_column_ids` and `consistency_group`
   exposed via the existing `database_view` upsert endpoint (additive, optional).

Out of scope: masking engine update for joint generation; UI for linked-column
selection. Both queued for Phase 54+.

## Plans

| Plan | Scope |
| --- | --- |
| **53-01** | Migration + custom-rules helper + detector layer 0 + discovery wire-up + DB column exposure |

---
*Created: 2026-05-16*
