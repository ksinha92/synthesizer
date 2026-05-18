"""OIDC provider integration using authlib.

Supports an arbitrary number of configured providers. The two callers wire up
today are:
- ``OIDCProvider.generic(settings)`` — issuer/client/secret from ``OIDC_*`` env.
- ``OIDCProvider.azure_ad(settings)`` — Microsoft Entra (Azure AD) from
  ``AZURE_AD_TENANT_ID`` + ``AZURE_AD_CLIENT_ID`` + ``AZURE_AD_CLIENT_SECRET``.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

import httpx
import redis.asyncio as aioredis
import structlog
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.config import Settings
from app.domain.shared.errors import AuthenticationError

logger = structlog.get_logger()

OIDC_STATE_TTL = 600  # 10 minutes
OIDC_STATE_PREFIX = "oidc_state:"


@dataclass(frozen=True)
class ProviderConfig:
    """Per-provider OIDC config — the bits that differ between issuers."""

    key: str  # e.g. "oidc", "azure_ad" — used in cookie/state namespacing
    issuer_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str
    provider_label: str  # stored on UserModel.sso_provider for traceability


class OIDCProvider:
    """Handles OIDC authentication flow with any compliant provider."""

    def __init__(self, settings: Settings, config: ProviderConfig | None = None) -> None:
        self._settings = settings
        self._redis: aioredis.Redis | None = None
        self._metadata: dict | None = None

        # Default to the generic OIDC provider for back-compat with existing call sites.
        self._cfg = config or ProviderConfig(
            key="oidc",
            issuer_url=settings.OIDC_ISSUER_URL,
            client_id=settings.OIDC_CLIENT_ID,
            client_secret=settings.OIDC_CLIENT_SECRET,
            redirect_uri=settings.OIDC_REDIRECT_URI,
            scopes=settings.OIDC_SCOPES,
            provider_label=settings.OIDC_ISSUER_URL,
        )

        if not self._cfg.issuer_url:
            self._configured = False
            return

        self._configured = True
        self._client = AsyncOAuth2Client(
            client_id=self._cfg.client_id,
            client_secret=self._cfg.client_secret,
            redirect_uri=self._cfg.redirect_uri,
            scope=self._cfg.scopes,
        )

    # --- Factory constructors ---

    @classmethod
    def generic(cls, settings: Settings) -> "OIDCProvider":
        return cls(settings)

    @classmethod
    def azure_ad(cls, settings: Settings) -> "OIDCProvider":
        return cls(
            settings,
            ProviderConfig(
                key="azure_ad",
                issuer_url=settings.azure_ad_issuer_url,
                client_id=settings.AZURE_AD_CLIENT_ID,
                client_secret=settings.AZURE_AD_CLIENT_SECRET,
                redirect_uri=settings.AZURE_AD_REDIRECT_URI,
                scopes=settings.AZURE_AD_SCOPES,
                provider_label="azure_ad",
            ),
        )

    @property
    def provider_label(self) -> str:
        return self._cfg.provider_label

    def _ensure_configured(self) -> None:
        if not self._configured:
            raise AuthenticationError(
                message=f"{self._cfg.key} provider not configured.",
                code=f"{self._cfg.key}_not_configured",
            )

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self._settings.REDIS_URL)
        return self._redis

    async def _discover_metadata(self) -> dict:
        """Fetch OIDC provider metadata from .well-known endpoint."""
        if self._metadata is not None:
            return self._metadata

        discovery_url = f"{self._cfg.issuer_url}/.well-known/openid-configuration"
        async with httpx.AsyncClient() as client:
            resp = await client.get(discovery_url, timeout=10.0)
            resp.raise_for_status()
            self._metadata = resp.json()
        return self._metadata

    async def get_authorization_url(self) -> tuple[str, str]:
        """Generate authorization URL with CSRF-safe state parameter.

        Returns:
            Tuple of (authorization_url, state)
        """
        self._ensure_configured()

        metadata = await self._discover_metadata()
        authorization_endpoint = metadata["authorization_endpoint"]

        state = secrets.token_urlsafe(32)
        redis_client = await self._get_redis()
        # Namespace state by provider key so a state issued for one provider
        # cannot be redeemed at another's callback.
        await redis_client.set(
            f"{OIDC_STATE_PREFIX}{self._cfg.key}:{state}", "1", ex=OIDC_STATE_TTL
        )

        url = (
            f"{authorization_endpoint}"
            f"?client_id={self._cfg.client_id}"
            f"&redirect_uri={self._cfg.redirect_uri}"
            f"&response_type=code"
            f"&scope={self._cfg.scopes.replace(' ', '+')}"
            f"&state={state}"
        )

        await logger.ainfo("sso_login_initiated", provider=self._cfg.key)
        return url, state

    async def exchange_code(self, code: str, state: str) -> dict:
        """Exchange authorization code for user info after validating state."""
        self._ensure_configured()

        redis_client = await self._get_redis()
        state_key = f"{OIDC_STATE_PREFIX}{self._cfg.key}:{state}"
        stored = await redis_client.getdel(state_key)

        if stored is None:
            await logger.awarning("sso_callback_failure", reason="invalid_state", provider=self._cfg.key)
            raise AuthenticationError(
                message="Invalid or expired state parameter. Possible CSRF attack.",
                code="invalid_state",
            )

        try:
            metadata = await self._discover_metadata()
            token_endpoint = metadata["token_endpoint"]

            async with httpx.AsyncClient() as http_client:
                token_response = await http_client.post(
                    token_endpoint,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self._cfg.redirect_uri,
                        "client_id": self._cfg.client_id,
                        "client_secret": self._cfg.client_secret,
                    },
                    timeout=10.0,
                )
                token_response.raise_for_status()
                tokens = token_response.json()

            id_token = tokens.get("id_token")
            if not id_token:
                raise AuthenticationError(
                    message="No id_token in provider response",
                    code="missing_id_token",
                )

            jwks_uri = metadata["jwks_uri"]
            async with httpx.AsyncClient() as http_client:
                jwks_resp = await http_client.get(jwks_uri, timeout=10.0)
                jwks_resp.raise_for_status()

            from authlib.jose import jwt as authlib_jwt

            claims = authlib_jwt.decode(id_token, jwks_resp.json())
            claims.validate()

            user_info = {
                "sub": claims.get("sub"),
                "email": claims.get("email") or claims.get("preferred_username"),
                "name": claims.get("name", claims.get("preferred_username", "")),
            }

            if not user_info["sub"] or not user_info["email"]:
                raise AuthenticationError(
                    message="id_token missing required claims (sub, email)",
                    code="incomplete_claims",
                )

            await logger.ainfo(
                "sso_callback_success",
                provider=self._cfg.key,
                email=user_info["email"],
                sub=user_info["sub"],
            )
            return user_info

        except AuthenticationError:
            raise
        except Exception as e:
            await logger.aerror("sso_callback_failure", reason=str(e), provider=self._cfg.key)
            raise AuthenticationError(
                message=f"OIDC token exchange failed: {e}",
                code="token_exchange_failed",
            ) from e
