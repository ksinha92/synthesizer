"""Authentication API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.shared.errors import AuthenticationError
from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.auth.jwt import (
    create_access_token,
    create_refresh_token,
    create_service_account_token,
    decode_token,
)
from app.infrastructure.auth.oidc import OIDCProvider
from app.infrastructure.auth.password import (
    WeakPasswordError,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.models.user import UserModel

logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request/Response Models ---


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    force_password_change: bool = False


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SsoProviderInfo(BaseModel):
    id: str
    label: str
    login_url: str


class SsoProvidersResponse(BaseModel):
    providers: list[SsoProviderInfo]


# --- SSO Endpoints ---


async def _handle_sso_callback(
    provider: OIDCProvider,
    code: str,
    state: str,
    session: AsyncSession,
):
    """Shared callback path: exchange code, upsert user, set cookies, redirect."""
    try:
        user_info = await provider.exchange_code(code, state)
    except AuthenticationError as e:
        if e.code == "invalid_state":
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_state", "detail": e.message},
            )
        raise HTTPException(
            status_code=401,
            detail={"error": e.code, "detail": e.message},
        )

    result = await session.execute(
        select(UserModel).where(UserModel.sso_subject_id == user_info["sub"])
    )
    user = result.scalar_one_or_none()

    if user:
        user.email = user_info["email"]
        user.full_name = user_info["name"]
        user.last_login_at = datetime.now(timezone.utc)
    else:
        user = UserModel(
            email=user_info["email"],
            full_name=user_info["name"],
            role="viewer",
            sso_subject_id=user_info["sub"],
            sso_provider=provider.provider_label,
            is_active=True,
            token_version=0,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)

    await session.flush()

    access_token = create_access_token(user.id, user.email, user.role, user.token_version)
    refresh_token = create_refresh_token(user.id, user.token_version)

    await logger.ainfo("sso_callback_success", user_id=str(user.id), email=user.email)

    response = RedirectResponse(url=settings.FRONTEND_URL, status_code=302)
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.get("/sso/login")
@limiter.limit("20/minute")
async def sso_login(request: Request):
    """Initiate SSO login flow. Redirects to OIDC provider."""
    oidc = OIDCProvider.generic(settings)
    try:
        url, _state = await oidc.get_authorization_url()
        return RedirectResponse(url=url)
    except AuthenticationError as e:
        raise HTTPException(status_code=503, detail={"error": e.code, "detail": e.message})


@router.get("/sso/callback")
@limiter.limit("20/minute")
async def sso_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
):
    """Handle OIDC provider callback. Creates/updates user and returns tokens."""
    return await _handle_sso_callback(OIDCProvider.generic(settings), code, state, session)


@router.get("/sso/azure_ad/login")
@limiter.limit("20/minute")
async def azure_ad_login(request: Request):
    """Initiate Azure AD login. Redirects to login.microsoftonline.com."""
    aad = OIDCProvider.azure_ad(settings)
    try:
        url, _state = await aad.get_authorization_url()
        return RedirectResponse(url=url)
    except AuthenticationError as e:
        raise HTTPException(status_code=503, detail={"error": e.code, "detail": e.message})


@router.get("/sso/azure_ad/callback")
@limiter.limit("20/minute")
async def azure_ad_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
):
    """Handle Azure AD callback. Reuses the shared OIDC upsert path."""
    return await _handle_sso_callback(OIDCProvider.azure_ad(settings), code, state, session)


# --- Local Password Login ---


def _set_auth_cookies(response, access_token: str, refresh_token: str) -> None:
    """Set the HttpOnly auth cookies the rest of the app reads."""
    is_prod = settings.ENVIRONMENT != "development"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        path="/api/v1/auth",
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/15minute")
async def login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate via email + password. Generic error message regardless of
    which check failed, so probes can't enumerate accounts."""
    from fastapi.responses import JSONResponse

    generic = HTTPException(
        status_code=401,
        detail={"error": "invalid_credentials", "detail": "Invalid email or password"},
    )

    email = (body.email or "").strip().lower()
    if not email or not body.password:
        raise generic

    # Case-insensitive lookup — the ux_users_email_lower index keeps this fast.
    result = await session.execute(
        select(UserModel).where(UserModel.email.ilike(email))
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not user.password_hash:
        await logger.awarning(
            "login_denied",
            reason="no_user_or_no_password",
            email=email,
            ip=request.client.host if request.client else "unknown",
        )
        raise generic

    if not verify_password(body.password, user.password_hash):
        await logger.awarning(
            "login_denied",
            reason="bad_password",
            user_id=str(user.id),
            ip=request.client.host if request.client else "unknown",
        )
        raise generic

    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()

    access_token = create_access_token(user.id, user.email, user.role, user.token_version)
    refresh_token = create_refresh_token(user.id, user.token_version)

    await logger.ainfo("login_success", user_id=str(user.id), email=user.email)

    profile = UserProfileResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        force_password_change=user.force_password_change,
    )
    payload = LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=profile,
    )
    response = JSONResponse(content=payload.model_dump())
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/change-password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Change the current user's password.

    Bumps ``token_version`` to invalidate all other active sessions, clears
    ``force_password_change``, and reissues fresh cookies for this session.
    """
    import uuid

    from fastapi.responses import JSONResponse

    user_id_raw = current_user.get("id")
    if not user_id_raw:
        raise HTTPException(
            status_code=400,
            detail={"error": "no_user_id", "detail": "Service accounts cannot change password"},
        )

    result = await session.execute(select(UserModel).where(UserModel.id == uuid.UUID(user_id_raw)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "user_not_found"})

    if not user.password_hash or not verify_password(body.current_password, user.password_hash):
        await logger.awarning(
            "change_password_denied",
            reason="bad_current_password",
            user_id=str(user.id),
        )
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_credentials", "detail": "Current password is incorrect"},
        )

    try:
        validate_password_strength(body.new_password)
    except WeakPasswordError as exc:
        await logger.awarning(
            "change_password_denied",
            reason="weak_new_password",
            rule=exc.message,
            user_id=str(user.id),
        )
        raise HTTPException(
            status_code=422,
            detail={"error": exc.code, "detail": exc.message},
        )

    if verify_password(body.new_password, user.password_hash):
        await logger.awarning(
            "change_password_denied",
            reason="new_equals_current",
            user_id=str(user.id),
        )
        raise HTTPException(
            status_code=422,
            detail={"error": "password_unchanged", "detail": "New password must differ from current"},
        )

    user.password_hash = hash_password(body.new_password)
    user.force_password_change = False
    user.password_changed_at = datetime.now(timezone.utc)
    user.token_version = user.token_version + 1  # invalidates other sessions
    await session.flush()

    access_token = create_access_token(user.id, user.email, user.role, user.token_version)
    refresh_token = create_refresh_token(user.id, user.token_version)

    await logger.ainfo("password_changed", user_id=str(user.id))

    response = JSONResponse(content={"ok": True})
    _set_auth_cookies(response, access_token, refresh_token)
    return response


# --- SSO Provider Discovery ---


@router.get("/sso/providers", response_model=SsoProvidersResponse)
async def sso_providers():
    """List the SSO providers the UI should render buttons for."""
    providers: list[SsoProviderInfo] = []
    if settings.OIDC_ISSUER_URL:
        providers.append(
            SsoProviderInfo(
                id="oidc",
                label="Sign in with SSO",
                login_url="/api/v1/auth/sso/login",
            )
        )
    if settings.azure_ad_configured:
        providers.append(
            SsoProviderInfo(
                id="azure_ad",
                label="Sign in with Microsoft",
                login_url="/api/v1/auth/sso/azure_ad/login",
            )
        )
    return SsoProvidersResponse(providers=providers)


# --- Service Account Token ---


@router.post("/token", response_model=TokenResponse)
@limiter.limit("10/minute")
async def create_token(request: Request, body: TokenRequest):
    """Create a JWT for service account authentication."""
    try:
        token = create_service_account_token(body.api_key)
    except AuthenticationError as e:
        await logger.awarning("token_invalid", reason=e.code, ip=request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=401,
            detail={"error": e.code, "detail": e.message},
        )

    await logger.ainfo("token_created", role="service_account", ip=request.client.host if request.client else "unknown")

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# --- Refresh Token ---


class RefreshRequestOptional(BaseModel):
    refresh_token: str | None = None


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    body: RefreshRequestOptional = RefreshRequestOptional(),
    session: AsyncSession = Depends(get_session),
):
    """Refresh an access token using a valid refresh token (body or cookie)."""
    token_value = body.refresh_token or request.cookies.get("refresh_token")
    if not token_value:
        raise HTTPException(
            status_code=401,
            detail={"error": "missing_token", "detail": "No refresh token provided"},
        )

    try:
        payload = decode_token(token_value)
    except Exception as exc:
        await logger.awarning(
            "token_invalid",
            reason="invalid_refresh",
            error=type(exc).__name__,
            ip=request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "detail": "Invalid or expired refresh token"},
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "detail": "Not a refresh token"},
        )

    import uuid
    user_id = uuid.UUID(payload["sub"])
    result = await session.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={"error": "user_not_found", "detail": "User not found or inactive"},
        )

    # Validate token version for revocation check
    token_ver = payload.get("ver", 0)
    if token_ver != user.token_version:
        await logger.awarning("token_invalid", reason="token_revoked", user_id=str(user_id))
        raise HTTPException(
            status_code=401,
            detail={"error": "token_revoked", "detail": "Refresh token has been revoked"},
        )

    access_token = create_access_token(user.id, user.email, user.role, user.token_version)

    await logger.ainfo("token_refresh", user_id=str(user.id))

    from fastapi.responses import JSONResponse
    is_prod = settings.ENVIRONMENT != "development"
    response = JSONResponse(content=TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    ).model_dump())
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


# --- Logout ---


@router.post("/logout")
async def logout():
    """Clear auth cookies."""
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={"ok": True})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    return response


# --- Current User ---


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get current user profile, including the force_password_change flag."""
    import uuid

    user_id = current_user.get("id")
    force_change = False
    if user_id and current_user.get("role") != "service_account":
        try:
            result = await session.execute(
                select(UserModel.force_password_change).where(UserModel.id == uuid.UUID(user_id))
            )
            force_change = bool(result.scalar_one_or_none())
        except Exception:
            # Pre-migration database (column not yet present), or transient
            # lookup failure — degrade gracefully rather than 500'ing /me.
            force_change = False
    return UserProfileResponse(
        id=current_user["id"] or "",
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        force_password_change=force_change,
    )


class ProfileUpdate(BaseModel):
    full_name: str


@router.put("/me", response_model=UserProfileResponse)
async def update_me(
    body: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update current user's display name."""
    import uuid

    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail={"error": "no_user_id", "detail": "Service accounts cannot update profile"})

    result = await session.execute(select(UserModel).where(UserModel.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "user_not_found"})

    user.full_name = body.full_name.strip()
    await session.flush()

    await logger.ainfo("profile_updated", user_id=user_id, full_name=user.full_name)

    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        force_password_change=user.force_password_change,
    )
