---
phase: 39-orphaned-features-ui
plan: 01
status: complete
completed: 2026-04-01
---

## What Was Done

Wired 4 orphaned backend features into the frontend UI, plus added 1 new backend endpoint (DLQ listing).

### AC-1: Schema Introspection Before Discovery ✓
- Added `fetchSchemas()` method + `schemas` state to `connection-store.ts`
- Created `schema-selector.tsx` — modal with checkbox list, select all/deselect all, loading state
- Wired into `run-discovery-button.tsx` — clicking "Run Discovery" now shows schema selector first
- Discovery page filters displayed schemas by user selection (client-side filter via `filteredSchemas`)

### AC-2: Webhook Management UI ✓
- Created `webhook-manager.tsx` — project selector dropdown, webhook list table, add form, delete with confirm
- Shows secret once after creation with copy-to-clipboard button
- Event checkboxes for job.completed / job.failed
- Wired to existing GET/POST/DELETE webhook endpoints

### AC-3: Encryption Key Rotation UI ✓
- Created `encryption-key-rotation.tsx` — info card with rotate button, confirmation dialog with warning
- New key input with generation command hint
- Red "Rotate Key" button in dialog (destructive action styling)
- Wired to existing POST /admin/rotate-encryption-key

### AC-4: Dead Letter Queue Viewer ✓
- Added `GET /admin/dead-letter-jobs` endpoint to `admin.py` (admin-only, paginated)
- Created `dead-letter-queue.tsx` — table with job ID, type, error, retry count, resolved status
- Green/red badges for resolved/unresolved entries
- Pagination support, empty state with checkmark icon

### Admin Page Updated ✓
- Expanded from 3 tabs to 6 tabs: Audit Log, Access Control, AI Settings, Webhooks, Security, Dead Letter Queue
- Added `overflow-x-auto` for tab scrolling on narrow screens

## Files Created
- `frontend/src/components/discovery/schema-selector.tsx`
- `frontend/src/components/admin/webhook-manager.tsx`
- `frontend/src/components/admin/encryption-key-rotation.tsx`
- `frontend/src/components/admin/dead-letter-queue.tsx`

## Files Modified
- `frontend/src/stores/connection-store.ts` — added fetchSchemas, schemas, schemasLoading
- `frontend/src/components/discovery/run-discovery-button.tsx` — schema selector integration
- `frontend/src/app/projects/[projectId]/discovery/page.tsx` — filteredSchemas, onSchemasSelected prop
- `frontend/src/app/admin/page.tsx` — 6 tabs, 3 new component imports
- `backend/app/api/v1/admin.py` — GET /admin/dead-letter-jobs endpoint

## Verification
- Backend `py_compile` passes ✓
- Frontend `next build` succeeds ✓
- Admin page: 8kB (up from 5.2kB with 3 new components) ✓
- Discovery page: 14.8kB (up from 14.3kB with schema selector) ✓

## Plan vs Actual Reconciliation

| Planned | Actual | Status |
|---------|--------|--------|
| AC-1: Schema selector modal | Built as planned | ✓ Match |
| AC-2: Webhook management tab | Built as planned, with project selector | ✓ Match |
| AC-3: Key rotation dialog | Built as planned | ✓ Match |
| AC-4: DLQ backend + frontend | Built as planned | ✓ Match |
| Modify `backend/app/api/v1/jobs.py` | DLQ endpoint added to `admin.py` instead | Deviation (better fit) |
| Modify `backend/.../job_repo.py` | Inline query in admin endpoint | Deviation (simpler) |
| `run-discovery-button.tsx` modified | Yes, but not in plan's files_modified list | Plan oversight |

### Deviations
- **DLQ endpoint location:** Plan listed `jobs.py` and `job_repo.py`, but the endpoint was added to `admin.py` with an inline SQLAlchemy query. This is consistent with how other admin endpoints work (audit-logs, members) — they query directly without a separate repo layer. Simpler and avoids creating a one-method repository.
- **run-discovery-button.tsx modified:** The plan's `files_modified` frontmatter didn't list this file, but the task description did call for wiring the schema selector into it. Minor plan inconsistency.

### Deferred Issues
- Schema selection is **UI-only filtering** — backend still discovers all schemas. A future enhancement could pass selected schemas to the discovery command to reduce scan time.
- Webhook management requires a **project selector** — if the user has many projects this could be unwieldy. A dedicated project-scoped settings page would be cleaner.
- DLQ viewer is **read-only** — no resolve or retry actions. Phase 42 or a future milestone could add these.
- **No integration tests** for the new DLQ endpoint or the 4 new frontend components.
