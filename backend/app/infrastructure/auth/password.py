"""Password hashing and strength validation for local credential auth."""

from __future__ import annotations

import re

from passlib.context import CryptContext

from app.domain.shared.errors import AuthenticationError

# bcrypt is the only scheme; deprecated="auto" lets us add a stronger one later
# without breaking existing hashes.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MIN_LENGTH = 8
_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SYMBOL = re.compile(r"[^A-Za-z0-9]")


class WeakPasswordError(AuthenticationError):
    """Raised when a candidate password does not meet strength requirements."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="weak_password")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of ``plain``."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    """Verify ``plain`` against a stored hash. Returns False if hash is missing."""
    if not hashed:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def validate_password_strength(plain: str) -> None:
    """Enforce the local-password complexity policy.

    Rules: >= 8 chars, at least one upper, one lower, one digit, one symbol.
    Raises :class:`WeakPasswordError` on the first failing rule.
    """
    if not plain or len(plain) < MIN_LENGTH:
        raise WeakPasswordError(f"Password must be at least {MIN_LENGTH} characters")
    if not _UPPER.search(plain):
        raise WeakPasswordError("Password must contain at least one uppercase letter")
    if not _LOWER.search(plain):
        raise WeakPasswordError("Password must contain at least one lowercase letter")
    if not _DIGIT.search(plain):
        raise WeakPasswordError("Password must contain at least one digit")
    if not _SYMBOL.search(plain):
        raise WeakPasswordError("Password must contain at least one symbol")
