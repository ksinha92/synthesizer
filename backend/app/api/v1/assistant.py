"""AI Assistant chat endpoint."""

from __future__ import annotations


import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

import uuid as _uuid

from app.infrastructure.ai.llm_provider import create_provider_from_runtime
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.rbac import assert_project_access
from app.infrastructure.persistence.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/assistant", tags=["assistant"])

MAX_MESSAGE_LENGTH = 2000

SYSTEM_PROMPT = """You are the DataWrangler AI Assistant — a helpful TDM platform assistant.
You help users with: querying PII status, suggesting masking strategies, checking job status,
explaining schemas, and navigating the platform.

You have access to this project context:
{context}

Be concise and actionable. Suggest specific next steps when relevant.
If the user asks about unmasked PII, suggest going to the masking page.
If they ask about data generation, suggest the synthetic page.
Do NOT perform write operations — only suggest actions for the user to take."""


class ChatRequest(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE_LENGTH)
    project_id: str
    context: dict = Field(default_factory=dict)  # {page: "discovery", ...}


class ChatAction(BaseModel):
    label: str
    href: str
    type: str = "navigate"


class ChatResponse(BaseModel):
    response: str
    actions: list[ChatAction] = []


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Chat with the AI assistant. Context-aware per project."""
    if len(body.message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(400, {"error": "message_too_long", "detail": f"Max {MAX_MESSAGE_LENGTH} characters"})

    # Membership check on the project_id supplied in the body — otherwise any
    # authenticated user could query any project's assistant context.
    try:
        proj_uuid = _uuid.UUID(body.project_id)
    except (TypeError, ValueError):
        raise HTTPException(400, {"error": "invalid_project_id"})
    await assert_project_access(proj_uuid, current_user, session, "viewer")

    provider = await create_provider_from_runtime()
    if not provider:
        raise HTTPException(503, {"error": "llm_unavailable", "detail": "No LLM provider configured. Go to Admin → AI Settings to configure."})

    # Build context
    project_context = f"Project ID: {body.project_id}\nCurrent page: {body.context.get('page', 'dashboard')}"

    prompt = SYSTEM_PROMPT.format(context=project_context) + f"\n\nUser: {body.message}"

    try:
        response_text = await provider.complete(prompt, max_tokens=500)
    except Exception as e:
        await logger.aerror("assistant_error", error=str(e))
        response_text = "I'm having trouble connecting to the AI service. Please try again."

    # Extract actions from response (rule-based)
    actions = _extract_actions(response_text, body.project_id)

    # Audit log
    await logger.ainfo(
        "assistant_chat",
        user_id=current_user.get("id"),
        project_id=body.project_id,
        message_length=len(body.message),
    )

    return ChatResponse(response=response_text, actions=actions)


def _extract_actions(response: str, project_id: str) -> list[ChatAction]:
    """Rule-based action extraction from assistant response."""
    actions = []
    lower = response.lower()

    if "mask" in lower and "pii" in lower:
        actions.append(ChatAction(label="Go to Masking", href=f"/projects/{project_id}/masking"))
    if "discover" in lower or "schema" in lower:
        actions.append(ChatAction(label="Run Discovery", href=f"/projects/{project_id}/discovery"))
    if "generat" in lower or "synthetic" in lower:
        actions.append(ChatAction(label="Generate Data", href=f"/projects/{project_id}/synthetic"))
    if "subset" in lower:
        actions.append(ChatAction(label="Configure Subset", href=f"/projects/{project_id}/subsetting"))
    if "workflow" in lower:
        actions.append(ChatAction(label="View Workflows", href=f"/projects/{project_id}/workflows"))
    if "job" in lower or "status" in lower:
        actions.append(ChatAction(label="View Jobs", href=f"/projects/{project_id}/jobs"))
    if "compliance" in lower or "report" in lower:
        actions.append(ChatAction(label="Compliance Reports", href=f"/projects/{project_id}/compliance"))

    return actions[:3]  # Max 3 actions


@router.get("/provider-status")
async def get_provider_status(
    current_user: dict = Depends(get_current_user),
):
    """Get current LLM provider name. Any authenticated user."""
    from app.infrastructure.ai.llm_settings import get_llm_settings
    s = await get_llm_settings()
    configured = s["has_api_key"] if s["provider"] == "claude" else bool(s["ollama_url"])
    return {"provider": s["provider"], "configured": configured}
