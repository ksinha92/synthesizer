"""Tests for the DI container's storage_backend provider.

Validates that Container.storage_backend() resolves to the correct concrete
StorageBackend subclass based on the STORAGE_BACKEND setting, without making
real boto3 calls. Uses dependency-injector's provider override API so we
never construct an S3 client against a live endpoint.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.container import Container
from app.infrastructure.storage.base import StorageBackend
from app.infrastructure.storage.local import LocalFilesystemStorage
from app.infrastructure.storage.s3 import S3Storage


@pytest.mark.parametrize(
    "storage_backend_value,expected_cls",
    [
        ("local", LocalFilesystemStorage),
        ("s3", S3Storage),
    ],
)
def test_container_storage_backend_resolves_to_correct_class(
    tmp_path, monkeypatch, storage_backend_value, expected_cls
):
    """Container.storage_backend() must return the concrete class implied by
    Settings.STORAGE_BACKEND, and the instance must be a StorageBackend.

    We override the Settings singleton with a stub configured for this case,
    so S3Storage is constructed with placeholder credentials (boto3.client
    is lazy — it does NOT make a network call on construction, so this is
    safe and does not require mocking the network).
    """
    # Build an isolated Settings instance with the desired backend.
    # ENVIRONMENT=test keeps the production-safety validator quiet.
    stub_settings = Settings(
        ENVIRONMENT="test",
        STORAGE_BACKEND=storage_backend_value,
        STORAGE_LOCAL_PATH=str(tmp_path),  # avoid writing to /data/storage
        S3_ENDPOINT_URL="http://localhost:9000",
        S3_BUCKET="test-bucket",
        S3_ACCESS_KEY="test-access",
        S3_SECRET_KEY="test-secret",
        S3_REGION="us-east-1",
    )

    container = Container()
    # Override the settings provider so the storage_backend selector picks
    # up our stub instead of reading the real environment.
    container.settings.override(stub_settings)

    try:
        # The DI container must expose a `storage_backend` provider.
        assert hasattr(container, "storage_backend"), (
            "Container is missing the `storage_backend` provider"
        )

        backend = container.storage_backend()

        assert isinstance(backend, expected_cls), (
            f"Expected {expected_cls.__name__} for STORAGE_BACKEND="
            f"{storage_backend_value!r}, got {type(backend).__name__}"
        )
        # Sanity check: it must still satisfy the StorageBackend contract.
        assert isinstance(backend, StorageBackend)
    finally:
        container.settings.reset_override()
