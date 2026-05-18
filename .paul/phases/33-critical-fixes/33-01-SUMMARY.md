---
phase: 33-critical-fixes
plan: 01
type: summary
---

# Phase 33 Summary: Critical UI Fixes (Blockers)

## Acceptance Criteria Results

### AC-1: Subsetting Connection Selector — PASS
- Added connection dropdown to subsetting-config.tsx using useConnectionStore
- Fetches connections on mount, replaces hardcoded "placeholder" with selected connectionId
- Analyze button disabled until both connection and root table selected

### AC-2: SSE Auth Token — PASS
- Rewrote use-sse.ts from native EventSource to fetch-based ReadableStream approach
- Uses `credentials: "include"` to send httpOnly cookies automatically
- Parses SSE `data:` lines from stream, handles reconnection gracefully
- AbortController for clean cleanup

### AC-3: RBAC Manager — PASS
- Replaced stub with full member management UI
- Member list via Ant Design Table (name, email, role dropdown, remove button)
- Invite form: email + role selector + send button
- Role change: inline dropdown calls PUT /api/v1/admin/members/{id}
- Remove: confirmation dialog + DELETE call
- Permission matrix table retained as reference

### AC-4: Connection Edit — PASS
- Added `updateConnection` method to connection-store (PUT endpoint)
- ConnectionFormDrawer accepts optional `editConnection` prop for edit mode
- When editing: title shows "Edit Connection", form pre-filled, button says "Update", submits PUT
- Connections page tracks editTarget state, passes to drawer
- ConnectionList onEdit handler passes connection data to page

### AC-5: Jobs Pagination — PASS
- Added page state to jobs page, wired onPageChange to setPage
- fetchJobs now accepts page param, builds URL with correct page number
- Filters reset page to 1 on change
- Pagination component rebuilt: supports arbitrary page counts with ellipsis
- Shows first, last, current ± 1 pages with "..." gaps

## Files Created
None

## Files Modified
- `frontend/src/components/subsetting/subsetting-config.tsx` — connection dropdown
- `frontend/src/hooks/use-sse.ts` — fetch-based SSE with credentials
- `frontend/src/components/admin/rbac-manager.tsx` — full member management
- `frontend/src/stores/connection-store.ts` — added updateConnection
- `frontend/src/components/connections/connection-form-drawer.tsx` — edit mode
- `frontend/src/components/connections/connection-list.tsx` — onEdit prop
- `frontend/src/app/projects/[projectId]/connections/page.tsx` — edit state
- `frontend/src/stores/job-store.ts` — page param in fetchJobs
- `frontend/src/app/projects/[projectId]/jobs/page.tsx` — page state wired
- `frontend/src/components/common/pagination.tsx` — ellipsis pagination

## Verification
- `npm run build` — clean build, zero errors
