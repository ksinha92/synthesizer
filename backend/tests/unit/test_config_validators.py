"""Tests for production-safety config validators."""

import pytest

from app.config import Settings


class TestSecretKeyValidator:
    def test_default_secret_key_allowed_in_dev(self):
        s = Settings(ENVIRONMENT="development", SECRET_KEY="change-me-in-production")
        assert s.SECRET_KEY == "change-me-in-production"

    def test_default_secret_key_rejected_in_prod(self):
        with pytest.raises(ValueError, match="must be changed"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="change-me-in-production",
                FERNET_KEY="6b4f3PrgT_R4S5J3T1bx5g2A7r6cV0fK_iJ8H9G1d-w=",
            )

    def test_short_secret_key_rejected_in_prod(self):
        with pytest.raises(ValueError, match="at least 32 bytes"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="too-short",
                FERNET_KEY="6b4f3PrgT_R4S5J3T1bx5g2A7r6cV0fK_iJ8H9G1d-w=",
            )

    def test_staging_also_enforced(self):
        with pytest.raises(ValueError, match="must be changed"):
            Settings(
                ENVIRONMENT="staging",
                SECRET_KEY="change-me-in-production",
                FERNET_KEY="6b4f3PrgT_R4S5J3T1bx5g2A7r6cV0fK_iJ8H9G1d-w=",
            )

    def test_test_environment_tolerates_defaults(self):
        s = Settings(ENVIRONMENT="test", SECRET_KEY="change-me-in-production")
        assert s.SECRET_KEY == "change-me-in-production"

    def test_strong_secret_key_accepted_in_prod(self):
        key = "a" * 32
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY=key,
            FERNET_KEY="6b4f3PrgT_R4S5J3T1bx5g2A7r6cV0fK_iJ8H9G1d-w=",  # fake but valid-length
            ADMIN_DEFAULT_PASSWORD="RotatedAdmin#Pa55w0rd",  # must differ from the seed default in prod
        )
        assert s.SECRET_KEY == key


class TestFernetKeyValidator:
    def test_empty_fernet_allowed_in_dev(self):
        s = Settings(ENVIRONMENT="development", FERNET_KEY="")
        assert s.FERNET_KEY == ""

    def test_empty_fernet_rejected_in_prod(self):
        with pytest.raises(ValueError, match="FERNET_KEY must be set"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                FERNET_KEY="",
                ADMIN_DEFAULT_PASSWORD="RotatedAdmin#Pa55w0rd",
            )
