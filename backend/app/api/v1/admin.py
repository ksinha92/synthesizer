"""Admin API endpoints — audit logs, system health, member management."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.rbac import require_admin
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.sqlalchemy.audit_repo import AuditRepository
from app.infrastructure.persistence.sqlalchemy.member_repo import MemberRepository

admin_logger = structlog.get_logger()
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs")
async def list_audit_logs(
    project_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """List audit logs. Admin only."""
    repo = AuditRepository(session)
    logs, total = await repo.list_logs(
        project_id=uuid.UUID(project_id) if project_id else None,
        user_id=uuid.UUID(user_id) if user_id else None,
        action=action,
        page=page,
        page_size=page_size,
    )
    return {"logs": logs, "total_count": total, "page": page, "page_size": page_size}


class RotateKeyRequest(BaseModel):
    new_key: str


@router.post("/rotate-encryption-key")
async def rotate_encryption_key(
    body: RotateKeyRequest,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Re-encrypt all connection credentials with a new Fernet key. Atomic."""
    from app.config import settings
    from app.infrastructure.security.encryption import CredentialEncryption
    from app.infrastructure.persistence.models.connection import ConnectionModel
    from sqlalchemy import select

    if not settings.FERNET_KEY:
        raise HTTPException(400, {"error": "no_fernet_key", "detail": "Current FERNET_KEY not set"})

    old_enc = CredentialEncryption(settings.FERNET_KEY)
    new_enc = CredentialEncryption(body.new_key)

    # Load all connections
    result = await session.execute(select(ConnectionModel))
    connections = result.scalars().all()

    if not connections:
        return {"rotated": 0, "message": "No connections to rotate"}

    # Verify first credential decrypts correctly
    first = connections[0]
    if first.credentials and "_encrypted" in first.credentials:
        try:
            old_enc.decrypt(first.credentials)
        except Exception as exc:
            await admin_logger.awarning(
                "fernet_rotation_probe_failed",
                connection_id=str(first.id),
                error=type(exc).__name__,
                user_id=current_user.get("id"),
            )
            raise HTTPException(400, {"error": "decrypt_failed", "detail": "Cannot decrypt with current key — verify FERNET_KEY is correct"})

    # Re-encrypt all
    rotated = 0
    for conn in connections:
        if conn.credentials:
            conn.credentials = old_enc.rotate(settings.FERNET_KEY, body.new_key, conn.credentials)
            rotated += 1

    await session.flush()

    # Audit log
    import structlog
    logger = structlog.get_logger()
    await logger.ainfo("encryption_key_rotated", rotated_count=rotated, user_id=current_user.get("id"))

    return {"rotated": rotated, "message": f"Successfully re-encrypted {rotated} connections. Update FERNET_KEY env var to the new key."}


# ── Member Management ─────────────────────────────────────────────────────


class MemberCreate(BaseModel):
    email: str
    role: str = "viewer"


class MemberRoleUpdate(BaseModel):
    role: str


VALID_ROLES = {"admin", "editor", "viewer"}


@router.get("/members")
async def list_members(
    page: int = 1,
    page_size: int = 50,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """List all team members. Admin only."""
    repo = MemberRepository(session)
    members, total = await repo.list_members(page=page, page_size=page_size)
    return {"members": members, "total_count": total, "page": page, "page_size": page_size}


@router.post("/members", status_code=201)
async def add_member(
    body: MemberCreate,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Add a team member by email. Admin only."""
    if body.role not in VALID_ROLES:
        raise HTTPException(400, {"error": "invalid_role", "detail": f"Role must be one of: {', '.join(VALID_ROLES)}"})

    repo = MemberRepository(session)

    user = await repo.find_user_by_email(body.email)
    if not user:
        raise HTTPException(404, {"error": "user_not_found", "detail": f"No user found with email {body.email}"})

    member = await repo.create_member(user_id=user.id, role=body.role)

    audit = AuditRepository(session)
    await audit.log(
        user_id=uuid.UUID(current_user["id"]) if current_user.get("id") else None,
        project_id=None, action="member_added",
        resource_type="member", resource_id=uuid.UUID(member["id"]),
        details={"email": body.email, "role": body.role},
    )

    return member


async def _assert_not_last_admin_demote(
    session: AsyncSession,
    member_id: uuid.UUID,
    new_role: str,
) -> None:
    """Refuse a role update that would leave the system with zero active admins.

    Concurrency-safe via row-level locks acquired **in deterministic order**.
    The earlier version locked the target row first, then the admin set —
    two parallel demotes against different targets locked rows in opposite
    orders and deadlocked under Postgres's deadlock detector. By selecting
    every currently active admin ``ORDER BY id ... FOR UPDATE`` in one shot,
    both transactions request the same rows in the same order; the second
    one queues behind the first instead of crossing locks.
    """
    from sqlalchemy import select

    from app.infrastructure.persistence.models.user import UserModel

    if new_role == "admin":
        return  # promoting to admin can never break the invariant

    # Single locking step: all currently active admins, in deterministic
    # order. This both materialises the "current" admin set for this
    # transaction and serialises any concurrent demote attempt.
    active_admins = (
        await session.execute(
            select(UserModel.id, UserModel.role, UserModel.is_active)
            .where(
                UserModel.role == "admin",
                UserModel.is_active == True,  # noqa: E712
            )
            .order_by(UserModel.id)
            .with_for_update()
        )
    ).all()

    # If the target isn't an active admin right now, this change can't
    # reduce the active-admin pool. (It could be inactive, already a
    # non-admin, or non-existent — the endpoint handles 404 separately.)
    target_is_active_admin = any(a.id == member_id for a in active_admins)
    if not target_is_active_admin:
        return

    remaining_after_change = len(active_admins) - 1
    if remaining_after_change < 1:
        raise HTTPException(
            400,
            {
                "error": "last_admin_protected",
                "detail": "Cannot demote the only remaining active admin. Promote another user to admin first.",
            },
        )


@router.put("/members/{member_id}")
async def update_member_role(
    member_id: uuid.UUID,
    body: MemberRoleUpdate,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Update a member's role. Admin only.

    Refuses two lock-out scenarios:

    * **Self-demotion** — an admin cannot demote their own row in the same
      request, otherwise the next call (including any "undo") would 403.
    * **Last-admin demotion** — refuses if it would drop the system to zero
      active admins.
    """
    if body.role not in VALID_ROLES:
        raise HTTPException(400, {"error": "invalid_role", "detail": f"Role must be one of: {', '.join(VALID_ROLES)}"})

    caller_id = current_user.get("id")
    if caller_id and str(member_id) == caller_id and body.role != "admin":
        raise HTTPException(
            400,
            {
                "error": "self_demotion_forbidden",
                "detail": "You cannot demote your own admin role. Ask another admin to do it.",
            },
        )

    await _assert_not_last_admin_demote(session, member_id, body.role)

    repo = MemberRepository(session)
    updated = await repo.update_member_role(member_id, body.role)
    if not updated:
        raise HTTPException(404, {"error": "not_found", "detail": "Member not found"})

    audit = AuditRepository(session)
    await audit.log(
        user_id=uuid.UUID(current_user["id"]) if current_user.get("id") else None,
        project_id=None, action="member_role_updated",
        resource_type="member", resource_id=member_id,
        details={"new_role": body.role},
    )

    return updated


@router.delete("/members/{member_id}", status_code=204)
async def remove_member(
    member_id: uuid.UUID,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Remove a team member. Admin only.

    Same safeguards as role update: an admin cannot remove their own row,
    and the only remaining admin cannot be soft-demoted to viewer.
    """
    caller_id = current_user.get("id")
    if caller_id and str(member_id) == caller_id:
        raise HTTPException(
            400,
            {
                "error": "self_removal_forbidden",
                "detail": "You cannot remove your own account. Ask another admin.",
            },
        )

    # delete_member is a soft-demote to viewer — that counts as "demote" for
    # the last-admin guard.
    await _assert_not_last_admin_demote(session, member_id, "viewer")

    repo = MemberRepository(session)
    deleted = await repo.delete_member(member_id)
    if not deleted:
        raise HTTPException(404, {"error": "not_found", "detail": "Member not found"})

    audit = AuditRepository(session)
    await audit.log(
        user_id=uuid.UUID(current_user["id"]) if current_user.get("id") else None,
        project_id=None, action="member_removed",
        resource_type="member", resource_id=member_id,
    )


# ── Dead Letter Queue ─────────────────────────────────────────────────────


@router.get("/dead-letter-jobs")
async def list_dead_letter_jobs(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """List dead letter queue entries. Admin only."""
    from sqlalchemy import func, select
    from app.infrastructure.persistence.models.job import DeadLetterJobModel

    base_query = select(DeadLetterJobModel)
    count_query = select(func.count()).select_from(DeadLetterJobModel)

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    query = base_query.order_by(DeadLetterJobModel.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
    result = await session.execute(query)

    items = [
        {
            "id": str(m.id),
            "original_job_id": str(m.original_job_id),
            "job_type": m.job_type,
            "error_message": m.error_message,
            "retry_count": m.retry_count,
            "resolved_at": m.resolved_at.isoformat() if m.resolved_at else None,
            "resolved_by": str(m.resolved_by) if m.resolved_by else None,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        }
        for m in result.scalars().all()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/dead-letter-jobs/{dlq_id}/resolve")
async def resolve_dead_letter_job(
    dlq_id: uuid.UUID,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Mark a dead letter queue entry as resolved. Admin only."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.infrastructure.persistence.models.job import DeadLetterJobModel

    result = await session.execute(
        select(DeadLetterJobModel).where(DeadLetterJobModel.id == dlq_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404, {"error": "not_found", "detail": "DLQ entry not found"})
    if entry.resolved_at:
        raise HTTPException(400, {"error": "already_resolved", "detail": "Entry already resolved"})

    entry.resolved_at = datetime.now(timezone.utc)
    entry.resolved_by = uuid.UUID(current_user["id"]) if current_user.get("id") else None
    await session.flush()

    return {"id": str(entry.id), "resolved_at": entry.resolved_at.isoformat()}


@router.post("/dead-letter-jobs/{dlq_id}/retry")
async def retry_dead_letter_job(
    dlq_id: uuid.UUID,
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Retry a dead letter queue entry by creating a new job. Admin only."""
    from sqlalchemy import select
    from app.infrastructure.persistence.models.job import DeadLetterJobModel, JobModel

    result = await session.execute(
        select(DeadLetterJobModel).where(DeadLetterJobModel.id == dlq_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404, {"error": "not_found", "detail": "DLQ entry not found"})

    # Find the original job to get project context
    orig_result = await session.execute(
        select(JobModel).where(JobModel.id == entry.original_job_id)
    )
    orig_job = orig_result.scalar_one_or_none()
    if not orig_job:
        raise HTTPException(400, {"error": "original_not_found", "detail": "Original job not found"})

    # Create a new pending job cloned from the original
    new_job = JobModel(
        project_id=orig_job.project_id,
        job_type=orig_job.job_type,
        reference_id=orig_job.reference_id,
        status="pending",
        progress=0,
        created_by=uuid.UUID(current_user["id"]) if current_user.get("id") else orig_job.created_by,
    )
    session.add(new_job)
    await session.flush()

    # Dispatch the matching Celery task so the replacement job actually runs.
    # Masking is not retryable from the DLQ alone because it requires the original
    # connection_id, which is neither stored on JobModel nor populated in payload today.
    project_id_str = str(orig_job.project_id)
    job_id_str = str(new_job.id)
    reference_id_str = str(orig_job.reference_id)
    dispatched = False

    if orig_job.job_type == "discovery":
        from app.infrastructure.messaging.discovery_tasks import run_discovery_task
        run_discovery_task.delay(reference_id_str, project_id_str, job_id_str)
        dispatched = True
    elif orig_job.job_type == "generation":
        from app.infrastructure.messaging.synthetic_tasks import run_generation_task
        run_generation_task.delay(reference_id_str, project_id_str, job_id_str)
        dispatched = True
    elif orig_job.job_type == "subsetting":
        from app.infrastructure.messaging.subsetting_tasks import run_subsetting_task
        run_subsetting_task.delay(reference_id_str, project_id_str, job_id_str)
        dispatched = True
    elif orig_job.job_type == "workflow":
        from app.infrastructure.messaging.workflow_tasks import run_workflow_task
        run_workflow_task.delay(reference_id_str, project_id_str, job_id_str)
        dispatched = True
    elif orig_job.job_type == "masking":
        # Recover connection_id from DLQ payload if available, else fail clearly.
        connection_id = (entry.payload or {}).get("connection_id") if entry.payload else None
        if connection_id:
            from app.infrastructure.messaging.masking_tasks import run_masking_task
            run_masking_task.delay(reference_id_str, str(connection_id), project_id_str, job_id_str)
            dispatched = True

    if not dispatched:
        # Roll back the placeholder job so the user isn't left with a stranded "pending" row.
        await session.delete(new_job)
        await session.flush()
        raise HTTPException(
            422,
            {
                "error": "retry_not_supported",
                "detail": f"Cannot auto-retry job_type={orig_job.job_type!r} from DLQ. Re-run the original action manually.",
            },
        )

    # Mark DLQ entry as resolved
    from datetime import datetime, timezone
    entry.resolved_at = datetime.now(timezone.utc)
    entry.resolved_by = uuid.UUID(current_user["id"]) if current_user.get("id") else None
    entry.retry_count = entry.retry_count + 1
    await session.flush()

    return {"job_id": str(new_job.id), "dlq_id": str(entry.id), "status": "pending"}


# ── LLM Settings ──────────────────────────────────────────────────────────


class LLMSettingsResponse(BaseModel):
    provider: str
    has_api_key: bool
    ollama_url: str
    ollama_model: str
    claude_model: str
    litellm_url: str = ""
    has_litellm_api_key: bool = False
    litellm_model: str = "gpt-4o-mini"
    litellm_verify_ssl: bool = True
    litellm_no_proxy: str = ""


class LLMSettingsUpdate(BaseModel):
    provider: str
    claude_api_key: str | None = None
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    litellm_url: str | None = None
    litellm_api_key: str | None = None
    litellm_model: str | None = None
    litellm_verify_ssl: bool | None = None
    litellm_no_proxy: str | None = None


class LLMTestResponse(BaseModel):
    success: bool
    latency_ms: int | None = None
    error: str | None = None
    provider: str


@router.get("/settings/llm", response_model=LLMSettingsResponse)
async def get_llm_settings_endpoint(
    current_user: dict = Depends(require_admin),
):
    """Get current LLM provider configuration. Admin only."""
    from app.infrastructure.ai.llm_settings import get_llm_settings
    return await get_llm_settings()


@router.put("/settings/llm", response_model=LLMSettingsResponse)
async def update_llm_settings_endpoint(
    body: LLMSettingsUpdate,
    current_user: dict = Depends(require_admin),
):
    """Update LLM provider configuration. Admin only."""
    if body.provider not in ("claude", "ollama", "litellm"):
        raise HTTPException(400, {"error": "invalid_provider", "detail": "Provider must be 'claude', 'ollama', or 'litellm'"})
    if body.provider == "litellm" and not (body.litellm_url or "").strip():
        raise HTTPException(400, {"error": "invalid_litellm_url", "detail": "LiteLLM provider requires a non-empty URL"})

    from app.infrastructure.ai.llm_settings import (
        UnreachableLLMEndpointError,
        get_llm_settings,
        save_llm_settings,
    )
    try:
        await save_llm_settings(body.model_dump())
    except UnreachableLLMEndpointError as exc:
        raise HTTPException(400, {"error": exc.code, "detail": exc.message})

    import structlog
    logger = structlog.get_logger()
    await logger.ainfo("llm_settings_updated", provider=body.provider, user_id=current_user.get("id"))

    return await get_llm_settings()


@router.post("/settings/llm/test", response_model=LLMTestResponse)
async def test_llm_connection(
    current_user: dict = Depends(require_admin),
):
    """Test connectivity to the configured LLM provider. Admin only."""
    import time
    from app.infrastructure.ai.llm_provider import create_provider_from_runtime

    provider = await create_provider_from_runtime()
    if not provider:
        return LLMTestResponse(success=False, error="No LLM provider configured. Set an API key or Ollama URL.", provider="none")

    start = time.monotonic()
    try:
        response = await provider.complete("Say hello in one word.", max_tokens=10)
        latency = round((time.monotonic() - start) * 1000)
        return LLMTestResponse(success=True, latency_ms=latency, provider=provider._config.provider_name)
    except Exception as e:
        latency = round((time.monotonic() - start) * 1000)
        return LLMTestResponse(success=False, latency_ms=latency, error=str(e), provider=provider._config.provider_name)
