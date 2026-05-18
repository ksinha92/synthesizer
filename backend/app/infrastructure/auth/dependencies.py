"""FastAPI auth dependencies for route protection."""

from __future__ import annotations

import uuid
from typing import Callable

import structlog
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.auth.jwt import decode_token
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.user import UserModel

logger = structlog.get_logger()

# Dev user for local development (no SSO needed)
_DEV_USER = {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "dev@ameritas.com",
    "role": "admin",
    "full_name": "Dev User",
    "token_version": 0,
    "force_password_change": False,
}

# Paths the user can hit even when ``force_password_change=True``. Everything
# else is 403'd until the password is rotated — closes the gap where the
# frontend redirect was the only thing gating non-rotated accounts.
_FORCE_PW_CHANGE_ALLOWED_PATHS = frozenset(
    {
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
        "/api/v1/auth/refresh",
        "/api/v1/auth/sso/providers",
    }
)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Extract and validate auth token, return current user.

    In development mode, returns a dev user when no token is present.
    Checks Authorization header (Bearer) first, then cookies.

    Raises:
        HTTPException 401: If token missing, invalid, expired, or user not found/inactive.
    """
    token = _extract_token(request)
    if not token:
        # Dev mode bypass — return dev user without auth
        if settings.ENVIRONMENT == "development":
            return _DEV_USER
        await logger.awarning("auth_denied", reason="missing_token", ip=request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=401,
            detail={"error": "missing_token", "detail": "Authentication required"},
        )

    try:
        payload = decode_token(token)
    except Exception:
        await logger.awarning("auth_denied", reason="invalid_token", ip=request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "detail": "Invalid or expired token"},
        )

    # Service accounts don't have DB records
    if payload.get("role") == "service_account":
        return {
            "id": None,
            "email": "service_account",
            "role": "service_account",
            "full_name": "Service Account",
        }

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "detail": "Token missing subject"},
        )

    result = await session.execute(
        select(UserModel).where(UserModel.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        await logger.awarning("auth_denied", reason="user_not_found", user_id=user_id)
        raise HTTPException(
            status_code=401,
            detail={"error": "user_not_found", "detail": "User not found"},
        )

    if not user.is_active:
        await logger.awarning("auth_denied", reason="user_inactive", user_id=user_id)
        raise HTTPException(
            status_code=401,
            detail={"error": "user_inactive", "detail": "User account is disabled"},
        )

    # Validate token_version on BOTH access and refresh tokens. Bumping
    # ``user.token_version`` (e.g. after a password change) now revokes all
    # outstanding access tokens at the next request, not just refresh tokens.
    token_ver = payload.get("ver", 0)
    if token_ver != user.token_version:
        await logger.awarning(
            "auth_denied",
            reason="token_revoked",
            user_id=user_id,
            token_type=payload.get("type"),
            token_ver=token_ver,
            user_ver=user.token_version,
        )
        raise HTTPException(
            status_code=401,
            detail={
                "error": "token_revoked",
                "detail": "Session has been revoked. Please sign in again.",
            },
        )

    # Force-password-change enforcement: any user with the flag set is locked
    # out of every endpoint except the small set needed to actually rotate
    # the password and log out. The frontend redirect was a UX hint; this is
    # the real gate.
    if user.force_password_change and request.url.path not in _FORCE_PW_CHANGE_ALLOWED_PATHS:
        await logger.awarning(
            "auth_denied",
            reason="password_change_required",
            user_id=user_id,
            path=request.url.path,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "password_change_required",
                "detail": "You must change your password before using the app.",
            },
        )

    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "token_version": user.token_version,
        "force_password_change": user.force_password_change,
    }


async def get_optional_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict | None:
    """Same as get_current_user but returns None instead of raising 401."""
    try:
        return await get_current_user(request, session)
    except HTTPException:
        return None


def require_role(required_role: str) -> Callable:
    """Returns a dependency that checks the user's role."""

    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] != required_role and current_user["role"] != "admin":
            raise HTTPException(
                status_code=403,
                detail={"error": "insufficient_permissions", "detail": f"Role '{required_role}' required"},
            )
        return current_user

    return role_checker


def _extract_token(request: Request) -> str | None:
    """Extract token from Authorization header or cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    return request.cookies.get("access_token")
