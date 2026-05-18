# Phase 50 Context — Unified Database View

> Discuss-phase output for v0.8.

## Vision

A single working surface for the project's columns. Merges read-only discovery
output with editable masking-rule selection. Left rail: schema/table tree.
Right pane: every column with status pill (Not sensitive / Protected /
Unprotected) and an inline generator dropdown that creates or updates a
masking rule on change.

## Goals

1. **Backend `GET /projects/{id}/database`** flat list of all columns the
   project sees, each row carrying:
   `{ schema_name, table_name, column_id, column_name, data_type, pii_type,
      pii_confidence, status, current_generator, rule_id|null }`
2. **Backend `POST /projects/{id}/database/columns/{column_id}/rule`**
   upserts a masking rule for the column. Body: `{ masking_type }`. Returns
   the new/updated rule id. Idempotent.
3. **Backend `DELETE /projects/{id}/database/columns/{column_id}/rule`**
   removes the rule (status → Unprotected).
4. **Frontend page** at `/projects/[id]/database` rendering the schema tree
   + column table. Inline generator picker fires the upsert/delete endpoints.
5. **Re-add "Database View" tab** to the workspace tab bar — it was
   intentionally removed in 48-01 cleanup pending this route.

## Constraints

- No new tables. Uses existing `discovered_*` + `masking_rules` schema.
- Reuses Phase 49's `DEFAULT_GENERATOR_BY_PII` map for the dropdown options.
- Reuses Privacy Hub's "Default" policy as the home for inline-created rules.

## Plans

| Plan | Scope |
| --- | --- |
| **50-01** | 3 endpoints + frontend page + tab re-add. Single plan since the slice is interconnected. |

---
*Created: 2026-05-16*
