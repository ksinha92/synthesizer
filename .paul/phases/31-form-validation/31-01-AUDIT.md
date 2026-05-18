# Enterprise Plan Audit Report

**Plan:** .paul/phases/31-form-validation/31-01-PLAN.md
**Audited:** 2026-03-31
**Verdict:** Conditionally Acceptable (accepted after upgrades applied)

---

## 1. Executive Verdict

The plan is directionally correct, targeting real technical debt (ad-hoc validation, inconsistent tables, absent loading states). Conditionally acceptable — the must-have upgrades below address form-field contract gaps, validation schema specificity, and migration safety risks. With upgrades applied, this is shippable.

## 2. What Is Solid

- **Correct dependency choice**: react-hook-form + zod + @hookform/resolvers already in package.json. No new deps needed.
- **Accurate form migration targets**: connection-form-drawer (13 useState calls, manual validate()), create-project-dialog, and synthetic config-form are the right candidates.
- **`.ant-scoped` CSS isolation**: inherits existing pattern from globals.css and both existing Ant Table components.
- **Well-drawn boundaries**: "DO NOT change component APIs or store interfaces" is the right constraint.
- **Skeleton scope**: project-list, job-list, dashboard are the highest-traffic loading states.

## 3. Enterprise Gaps Identified

- RBAC manager migration is premature (static placeholder, will be rewritten)
- form-field.tsx contract underspecified (needs text, number, password-toggle, textarea, select)
- No accessibility specification (aria-invalid, aria-describedby, role="alert")
- Validation schema rules unspecified (port range, JSON parsing, trim, bounds)
- Project-list has dual view modes (card + table) — risk of destroying card view
- No verification for submission behavior parity (payload shape, test-connection flow, reset)
- No bundle impact note for new Ant Design route imports

## 4. Upgrades Applied to Plan

### Must-Have (Release-Blocking)

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| M1 | RBAC manager is a placeholder — migration is throwaway work | files_modified, tasks, boundaries | Removed rbac-manager.tsx from scope. Added boundary: "DO NOT migrate rbac-manager.tsx" |
| M2 | form-field.tsx contract underspecified | Task 1 | Specified field types (text, number, password+toggle, textarea, select), control prop, aria attributes |
| M3 | Validation schema rules unspecified | Tasks 3, 4, 5 | Added explicit zod rules: port 1-65535, name min/max, rowCount bounds, JSON refine, Snowflake conditionals |
| M4 | No verification for submission behavior parity | AC-1, verification | Added: identical payloads, test-connection flow, form reset on cancel/close |
| M5 | Project-list dual view mode risk | Task 6, AC-3, boundaries, verification | Explicitly scoped to table-view branch only. Card view preserved. |

### Strongly Recommended

| # | Finding | Plan Section Modified | Change Applied |
|---|---------|----------------------|----------------|
| S1 | No accessibility on form errors | Task 1, verification | Added aria-invalid, aria-describedby, role="alert" requirements |
| S2 | String fields should trim via zod | Tasks 3, 4 | Added z.transform(v => v.trim()) on string fields |
| S3 | extraParams JSON field silently swallows parse errors | Task 3 | Added .refine() validation for parseable JSON |

### Deferred (Can Safely Defer)

| # | Finding | Rationale for Deferral |
|---|---------|----------------------|
| D1 | Bundle-size analysis for new Ant Design route imports | Ant Design already in bundle; incremental cost of Table in 2 more routes is small |
| D2 | Skeleton variants for charts | No chart-heavy pages need skeletons yet |
| D3 | Server-side 422 error mapping to field-level errors | Separate concern, not in scope |

## 5. Audit & Compliance Readiness

- **Evidence**: `npm run build` zero errors + zero new warnings. Manual test of all 3 forms (empty submit → errors, valid submit → success, cancel → reset, connection test-connection flow).
- **High-risk file**: connection-form-drawer.tsx (278 lines, 13 state vars, conditional Snowflake fields, save-then-test, password toggle). Must verify all 4 connector types.
- **Subsetting table**: conditional render (only when analysis.length > 0). Verification must include triggering analysis.

## 6. Final Release Bar

1. All 3 form migrations produce identical payloads to same store methods
2. form-field.tsx handles text, number, password+toggle, textarea, select with aria-invalid + aria-describedby
3. Zod schemas enforce port range, trimming, JSON validation, bounds
4. Project-list card view untouched; only table-view branch uses Ant Design Table
5. RBAC manager excluded from scope
6. `npm run build` passes cleanly
7. Skeleton loading states render without layout shift
8. No new `any` types; all zod schemas produce inferred types used in useForm generic

---

**Summary:** Applied 5 must-have + 3 strongly-recommended upgrades. Deferred 3 items.
**Plan status:** Updated and ready for APPLY.

---
*Audit performed by PAUL Enterprise Audit Workflow*
