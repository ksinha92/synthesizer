"""Unit tests for the local password hashing + strength module."""

import pytest

from app.infrastructure.auth.password import (
    WeakPasswordError,
    hash_password,
    validate_password_strength,
    verify_password,
)


class TestHashing:
    def test_hash_then_verify_roundtrip(self):
        h = hash_password("Admin@12345")
        assert verify_password("Admin@12345", h)

    def test_wrong_password_fails(self):
        h = hash_password("Admin@12345")
        assert not verify_password("admin@12345", h)
        assert not verify_password("WrongPassword!1", h)

    def test_verify_returns_false_for_missing_hash(self):
        assert verify_password("any", None) is False
        assert verify_password("any", "") is False

    def test_verify_returns_false_for_garbage_hash(self):
        # Should not raise — passlib treats malformed hashes as a verify failure.
        assert verify_password("Admin@12345", "$2b$totally-not-a-hash") is False


class TestStrength:
    def test_accepts_strong_password(self):
        validate_password_strength("Admin@12345")
        validate_password_strength("Aa1!aaaa")  # exactly 8 chars

    @pytest.mark.parametrize(
        "candidate,fragment",
        [
            ("short", "at least 8"),
            ("alllower1!", "uppercase"),
            ("ALLUPPER1!", "lowercase"),
            ("NoDigits!", "digit"),
            ("NoSymbol12", "symbol"),
            ("", "at least 8"),
        ],
    )
    def test_rejects_weak_password(self, candidate, fragment):
        with pytest.raises(WeakPasswordError) as excinfo:
            validate_password_strength(candidate)
        assert fragment.lower() in excinfo.value.message.lower()
