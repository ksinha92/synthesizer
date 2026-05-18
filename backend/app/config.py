"""Application configuration via Pydantic Settings."""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/datawrangler"
    DATABASE_URL_SYNC: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "change-me-in-production"

    # CORS — defaults cover the common local-dev frontend ports. Add deployed
    # origins via the CORS_ORIGINS env var. Use `["*"]` only for development;
    # `allow_credentials=True` plus wildcard is rejected by browsers, so the
    # explicit list is the production-safe path.
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3942",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # Logging
    LOG_LEVEL: str = "INFO"

    # LLM (placeholders for Phase 6)
    LLM_PROVIDER: str = "claude"
    CLAUDE_API_KEY: str = ""
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    # LiteLLM (OpenAI-compatible proxy — works with Azure OpenAI, Bedrock, on-prem gateways, etc.)
    LITELLM_URL: str = ""
    LITELLM_API_KEY: str = ""
    LITELLM_MODEL: str = "gpt-4o-mini"
    LITELLM_VERIFY_SSL: bool = True
    LITELLM_NO_PROXY: str = ""  # Comma-separated hosts/CIDRs to bypass HTTP(S)_PROXY

    # Storage
    STORAGE_BACKEND: str = "local"  # local | s3
    STORAGE_LOCAL_PATH: str = "/data/storage"
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = "datawrangler"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # Encryption
    FERNET_KEY: str = ""  # Generated with Fernet.generate_key()

    # Auth — OIDC / SSO
    OIDC_ISSUER_URL: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/sso/callback"
    OIDC_SCOPES: str = "openid email profile"

    # Auth — JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # Auth — Service Accounts
    SERVICE_ACCOUNT_API_KEYS: list[str] = []

    # Auth — Rate Limiting
    AUTH_RATE_LIMIT: str = "10/minute"

    # Auth — Local password / seeded admin
    ADMIN_DEFAULT_EMAIL: str = "admin@ameritas.local"
    ADMIN_DEFAULT_PASSWORD: str = "Admin@12345"
    ADMIN_DEFAULT_FULL_NAME: str = "Default Admin"

    # Auth — Azure AD (configurable OIDC provider)
    AZURE_AD_TENANT_ID: str = ""
    AZURE_AD_CLIENT_ID: str = ""
    AZURE_AD_CLIENT_SECRET: str = ""
    AZURE_AD_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/sso/azure_ad/callback"
    AZURE_AD_SCOPES: str = "openid email profile"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Environment
    ENVIRONMENT: str = "development"

    @field_validator("DATABASE_URL_SYNC", mode="before")
    @classmethod
    def derive_sync_url(cls, v: str, info) -> str:
        if v:
            return v
        async_url = info.data.get("DATABASE_URL", "")
        return async_url.replace("+asyncpg", "+psycopg2")

    @model_validator(mode="after")
    def enforce_production_safety(self) -> "Settings":
        """Refuse to boot with insecure defaults in staging/production.

        Field-level validators cannot reliably see ENVIRONMENT because it is
        declared after the security fields, so this runs after all fields are
        populated. "development" and "test" tolerate placeholder secrets so
        the unit/integration suite can boot with the example .env values.
        """
        if self.ENVIRONMENT not in {"staging", "production"}:
            return self

        if self.SECRET_KEY == "change-me-in-production":
            raise ValueError(
                "SECRET_KEY must be changed from default value in non-development environments"
            )
        # HS256 needs at least 32 bytes (HMAC-SHA256 digest size).
        if len(self.SECRET_KEY.encode("utf-8")) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 bytes in non-development environments"
            )
        if not self.FERNET_KEY:
            raise ValueError(
                "FERNET_KEY must be set in non-development environments — "
                "generate one with: python -c "
                "'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        if self.ADMIN_DEFAULT_PASSWORD == "Admin@12345":
            raise ValueError(
                "ADMIN_DEFAULT_PASSWORD must be changed from default in non-development environments"
            )
        return self

    @property
    def azure_ad_configured(self) -> bool:
        return bool(self.AZURE_AD_TENANT_ID and self.AZURE_AD_CLIENT_ID and self.AZURE_AD_CLIENT_SECRET)

    @property
    def azure_ad_issuer_url(self) -> str:
        if not self.AZURE_AD_TENANT_ID:
            return ""
        return f"https://login.microsoftonline.com/{self.AZURE_AD_TENANT_ID}/v2.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
