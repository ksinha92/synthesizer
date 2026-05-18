"""JWT token creation and validation."""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings
from app.domain.shared.errors import AuthenticationError

# TODO: Use RS256/ES256 with asymmetric keys in production instead of HS256


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    role: str,
    token_version: int = 0,
) -> str:
    """Create a signed JWT access token.

    The ``ver`` claim mirrors ``user.token_version`` so the auth dependency
    can revoke active access tokens (not just refresh tokens) by bumping the
    user's version — e.g. after a password change.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID, token_version: int = 0) -> str:
    """Create a signed JWT refresh token with version for revocation."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Raises:
        AuthenticationError: If token is invalid, expired, or tampered.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if not payload.get("sub"):
            raise AuthenticationError(
                message="Token missing subject claim",
                code="invalid_token",
            )
        return payload
    except JWTError as e:
        raise AuthenticationError(
            message=f"Invalid token: {e}",
            code="invalid_token",
        ) from e


def create_service_account_token(api_key: str) -> str:
    """Create a JWT for a service account after validating the API key.

    Uses constant-time comparison to prevent timing attacks.

    Raises:
        AuthenticationError: If API key is invalid.
    """
    if not settings.SERVICE_ACCOUNT_API_KEYS:
        raise AuthenticationError(
            message="No service account API keys configured",
            code="no_api_keys",
        )

    # Constant-time comparison against all configured keys
    key_valid = any(
        hmac.compare_digest(api_key.encode(), configured_key.encode())
        for configured_key in settings.SERVICE_ACCOUNT_API_KEYS
    )

    if not key_valid:
        raise AuthenticationError(
            message="Invalid API key",
            code="invalid_api_key",
        )

    now = datetime.now(timezone.utc)
    payload = {
        "sub": "service_account",
        "role": "service_account",
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
