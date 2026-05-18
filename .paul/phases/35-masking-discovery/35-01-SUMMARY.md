---
phase: 35-masking-discovery
plan: 01
type: summary
---

# Phase 35 Summary: Masking + Synthetic + Discovery Completion

## Acceptance Criteria Results

### AC-1: Masking Rule Application — PASS
- Added `addRule` method to masking-store (POST to policy rules endpoint with column_id + strategy)
- Masking page: policy selector dropdown, per-suggestion "Apply" button, "Apply All to Policy" bulk action
- Applied rules tracked in state with checkmark indicators
- Auto-select first policy for convenience

### AC-2: Relationship Graph from API — PASS
- Added `relationships` state + `fetchRelationships` method to discovery-store
- Fetches from `/api/v1/projects/{projectId}/discovery/relationships`
- Fallback: derives FK relationships from column metadata (is_foreign_key columns)
- Discovery page fetches relationships when graph tab becomes active
- Passes real data to RelationshipGraph component instead of empty array

### AC-3: Quality Report Real Data — PASS
- Extended QualityData interface: column_scores now includes optional `distribution` array per column
- Distribution charts use API data when available, fall back to sample data when not
- Added `correlation_matrix` field: uses API original/synthetic matrices and column names when returned
- Privacy metrics already used real data from API response

### AC-4: Workflow Editor Structured Form — PASS
- Replaced raw JSON textarea with structured node builder
- Add/remove steps with dropdown per node (discover, mask, generate, subset, export)
- Color-coded node indicators matching workflow canvas colors
- Visual pipeline preview: colored badges with arrows showing flow
- Auto-generates DAG JSON from node list (sequential edges)
- Wrapped in AccessibleDialog with focus trap + Escape + aria

## Files Modified
- `frontend/src/stores/masking-store.ts` — addRule method
- `frontend/src/app/projects/[projectId]/masking/page.tsx` — policy selector, apply buttons
- `frontend/src/stores/discovery-store.ts` — relationships state, fetchRelationships
- `frontend/src/app/projects/[projectId]/discovery/page.tsx` — fetch relationships on graph tab
- `frontend/src/components/synthetic/quality-report.tsx` — real distribution + correlation data
- `frontend/src/components/workflows/workflow-editor.tsx` — structured form with preview

## Verification
- `npm run build` — clean build, zero errors
