---
phase: 34-dashboard-stats
plan: 01
type: summary
---

# Phase 34 Summary: Dashboard + Stats Wiring

## Acceptance Criteria Results

### AC-1: Dashboard Stats from API — PASS
- All 4 stats fetched in parallel via Promise.allSettled: projects count, active jobs (status=running), masking policies count, today's jobs count.
- Graceful fallback to 0 on any API error.
- Skeleton loading while fetching.

### AC-2: Project Detail Stats — PASS
- Fetches 4 counts per project: connections, discovery schemas, masking policies, synthetic configs.
- Uses Promise.allSettled for resilience — any failing endpoint returns 0.
- Shows SkeletonStatCard while loading instead of "—".
- All stat cards link to their respective pages.

### AC-3: PII Heatmap + Donut from API — PASS
- Dashboard attempts to fetch from /api/v1/dashboard/pii-summary.
- If API returns data: heatmap and donut use real tables/counts.
- If API fails or no discovery data: falls back to sample data with "Sample data" label.
- PII donut aggregates detected/masked/pending from heatmap table data.

### AC-4: Job Events → Notifications — PASS
- Jobs page tracks previous job statuses via useRef.
- On each poll (10s interval), detects status transitions.
- When job transitions to "completed" or "failed", calls addNotification on notification store.
- Notification includes job type and error message if failed.

## Files Modified
- `frontend/src/app/page.tsx` — 4 parallel stat fetches, PII data from API with fallback
- `frontend/src/app/projects/[projectId]/page.tsx` — 4 project stat counts, skeleton loading
- `frontend/src/app/projects/[projectId]/jobs/page.tsx` — job status change detection → notifications

## Verification
- `npm run build` — clean build, zero errors
