---
phase: 38-backend-api-gaps
plan: 01
status: complete
completed: 2026-04-01
---

## What Was Done

Built 8 new backend API endpoints across 4 routers to close gaps where the frontend was calling non-existent handlers.

### AC-1: RBAC Member Management (4 endpoints) ✓
- Created `ProjectMemberModel` ORM model (`backend/app/infrastructure/persistence/models/member.py`) mapping to existing `project_members` table from migration 010
- Created `MemberRepository` (`backend/app/infrastructure/persistence/sqlalchemy/member_repo.py`) with list, create, update role, delete, and user lookup by email
- Added 4 endpoints to `backend/app/api/v1/admin.py`:
  - `GET /admin/members` — paginated member list with joined user email/name
  - `POST /admin/members` — add member by email lookup + role assignment
  - `PUT /admin/members/{member_id}` — update role
  - `DELETE /admin/members/{member_id}` — remove member (204)
- All endpoints admin-only with audit logging
- Response shape matches frontend `Member` interface: `{id, email, full_name, role, added_at}`

### AC-2: Subset Config Listing ✓
- Added `GET /projects/{project_id}/subset/configs` to `backend/app/api/v1/subsetting.py`
- Uses existing `SubsettingRepository.find_by_project_id()` method
- Returns full config details including root_tables and traversal_strategy

### AC-3: Masking Rule Update + Delete ✓
- Added `RuleUpdate` Pydantic model for partial updates
- Added `PUT /projects/{project_id}/masking/policies/{policy_id}/rules/{rule_id}` — partial update with policy ownership verification
- Added `DELETE /projects/{project_id}/masking/policies/{policy_id}/rules/{rule_id}` — delete with 204 response
- Added `update_rule()` and `delete_rule()` to `SQLAlchemyMaskingRepository`
- Both endpoints verify rule belongs to specified policy and write audit logs

### AC-4: Workflow Execution History ✓
- Added `GET /projects/{project_id}/workflows/{workflow_id}/executions` to `backend/app/api/v1/workflows.py`
- Queries `jobs` table filtering by `job_type="workflow"` and `reference_id=workflow_id`
- Paginated response: `{items, total, page, page_size}`
- Each item: `{id, status, progress, started_at, completed_at, error_message, created_at}`

## Files Modified
- `backend/app/api/v1/admin.py` — 4 new member endpoints + Pydantic models
- `backend/app/api/v1/masking.py` — 2 new rule CRUD endpoints + RuleUpdate model
- `backend/app/api/v1/subsetting.py` — 1 new listing endpoint
- `backend/app/api/v1/workflows.py` — 1 new executions endpoint

## Files Created
- `backend/app/infrastructure/persistence/models/member.py` — ProjectMemberModel ORM
- `backend/app/infrastructure/persistence/sqlalchemy/member_repo.py` — MemberRepository

## Files Updated
- `backend/app/infrastructure/persistence/sqlalchemy/masking_repo.py` — update_rule + delete_rule methods

## Verification
- All 7 modified/created files pass `py_compile` syntax check ✓
- Frontend `next build` succeeds (no frontend changes made) ✓
- No new migrations needed (project_members table already exists) ✓

## Plan vs Actual Reconciliation

| Planned | Actual | Status |
|---------|--------|--------|
| AC-1: 4 RBAC member endpoints | 4 endpoints built exactly as planned | ✓ Match |
| AC-2: Subset config listing | 1 endpoint, reused existing repo method | ✓ Match |
| AC-3: Masking rule PUT + DELETE | 2 endpoints + 2 repo methods | ✓ Match |
| AC-4: Workflow execution history | 1 endpoint querying jobs table | ✓ Match |
| Domain entity for ProjectMember | Skipped — used ORM model + repo dict directly | Deviation (simpler) |
| Application handler layer | Skipped — endpoints call repo directly | Deviation (simpler) |

### Deviations
- **Skipped domain entity + handler layer for members:** The plan called for `backend/app/domain/admin/entities.py` and `backend/app/application/admin/handlers.py`. These were unnecessary — the member CRUD is simple enough that the router calls the repository directly, consistent with how `audit-logs` and `llm-settings` already work in the same file. No business logic warranting a domain layer.
- **Member model file path:** Plan said `models/rbac.py`, actual is `models/member.py` — clearer name.

### Deferred Issues
- Members are currently **global** (not project-scoped) — the `project_id` field on `project_members` is set to a zero UUID. Future work could scope members per project.
- No **duplicate member check** on POST — if the same user is added twice, a DB unique constraint error will fire. Could add a friendlier 409 response.
- **Integration tests** for the 8 new endpoints are not yet written (deferred to Phase 42 or a testing phase).
