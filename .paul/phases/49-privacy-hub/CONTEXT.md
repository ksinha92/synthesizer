# Phase 49 Context — Privacy Hub Dashboard

> Discuss-phase output for v0.8.

## Vision

Replace the current stat-card-heavy project landing page with a goal-driven
**Privacy Hub** — three counters (sensitive / protected / unprotected),
recommended generators grouped by PII type with a one-click "Apply all"
bulk action, and the existing activity feed underneath. The hub's job is to
walk users toward zero unprotected sensitive columns.

## Goals

1. **Backend aggregate endpoint** `GET /api/v1/projects/{id}/privacy-hub`
   returning: total sensitive, protected (= columns with at least one
   matching masking rule), unprotected, and recommended-generator groups
   (one entry per PII type with the unprotected column count + a default
   generator suggestion).
2. **Backend bulk action** `POST /api/v1/projects/{id}/privacy-hub/apply-all`
   accepting a list of PII types and creating default masking rules for
   every unprotected column of those types.
3. **Frontend `<PrivacyHub>` component** rendering the three counters,
   the recommended-generators panel, and the activity feed. Keeps the
   existing project metadata banner.
4. **Wire into the project landing page** (`projects/[id]/page.tsx`).

## Constraints

- No new domain types. Reuse the existing `discovered_columns` + `masking_rules`
  tables for both counts and rule creation.
- Default-generator-per-PII-type map lives in a small infrastructure helper —
  no DB migration; can become a table later if customization is needed.
- "Apply all" is idempotent: re-running it on the same set does not duplicate
  rules (skip columns that already have a matching rule).

## Plans

| Plan | Scope |
| --- | --- |
| **49-01** | Endpoint pair + frontend component + page wiring + unit tests for the aggregator + bulk action. |

---
*Created: 2026-05-16*
