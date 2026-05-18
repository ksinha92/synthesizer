"""Dependency injection container."""

from dependency_injector import containers, providers

from app.config import Settings
from app.infrastructure.ai.llm_provider import create_provider
from app.infrastructure.auth.oidc import OIDCProvider
from app.infrastructure.connectors.registry import create_registry
from app.infrastructure.storage.base import StorageBackend
from app.infrastructure.storage.local import LocalFilesystemStorage
from app.infrastructure.storage.s3 import S3Storage


def _build_storage_backend(settings: Settings) -> StorageBackend:
    """Construct the configured StorageBackend.

    Centralizes the local/s3 selection so call sites don't branch on
    ``settings.STORAGE_BACKEND`` themselves.
    """
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage(
            endpoint_url=settings.S3_ENDPOINT_URL,
            bucket=settings.S3_BUCKET,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            region=settings.S3_REGION,
        )
    return LocalFilesystemStorage(settings.STORAGE_LOCAL_PATH)


class Container(containers.DeclarativeContainer):
    """Application DI container. Wires infrastructure to domain."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.api.v1.health",
            "app.api.v1.auth",
            "app.api.v1.projects",
            "app.api.v1.connections",
            "app.api.v1.discovery",
            "app.api.v1.synthetic",
            "app.api.v1.masking",
            "app.api.v1.subsetting",
            "app.api.v1.workflows",
            "app.api.v1.jobs",
            "app.api.v1.compliance",
            "app.api.v1.admin",
            "app.api.v1.assistant",
            "app.api.v1.events",
            "app.infrastructure.auth.dependencies",
        ],
    )

    config = providers.Configuration()

    settings = providers.Singleton(Settings)

    oidc_provider = providers.Singleton(
        OIDCProvider,
        settings=settings,
    )

    connector_registry = providers.Singleton(create_registry)

    llm_provider = providers.Singleton(
        create_provider,
        settings=settings,
    )

    storage_backend = providers.Singleton(
        _build_storage_backend,
        settings=settings,
    )
