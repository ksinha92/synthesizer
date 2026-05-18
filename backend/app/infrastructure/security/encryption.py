"""Fernet encryption for connection credentials at rest."""

from __future__ import annotations

import json

import structlog
from cryptography.fernet import Fernet, InvalidToken

logger = structlog.get_logger()

ENCRYPTED_MARKER = "_encrypted"


class CredentialEncryption:
    """Encrypts/decrypts connection credentials using Fernet symmetric encryption."""

    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("FERNET_KEY is required for credential encryption")
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, data: dict) -> dict:
        """Encrypt credentials dict → {_encrypted: ciphertext}."""
        plaintext = json.dumps(data).encode()
        ciphertext = self._fernet.encrypt(plaintext)
        return {ENCRYPTED_MARKER: ciphertext.decode()}

    def decrypt(self, data: dict) -> dict:
        """Decrypt {_encrypted: ciphertext} → credentials dict."""
        if ENCRYPTED_MARKER not in data:
            # Legacy plaintext — return as-is (pre-migration)
            return data

        try:
            ciphertext = data[ENCRYPTED_MARKER].encode()
            plaintext = self._fernet.decrypt(ciphertext)
            return json.loads(plaintext)
        except (InvalidToken, json.JSONDecodeError) as e:
            logger.error("credential_decrypt_failed", error=str(e))
            raise ValueError("Failed to decrypt credentials — key may be incorrect") from e

    def rotate(self, old_key: str, new_key: str, data: dict) -> dict:
        """Re-encrypt credentials from old key to new key."""
        old_fernet = Fernet(old_key.encode())
        new_fernet = Fernet(new_key.encode())

        if ENCRYPTED_MARKER not in data:
            # Plaintext — just encrypt with new key
            plaintext = json.dumps(data).encode()
            ciphertext = new_fernet.encrypt(plaintext)
            return {ENCRYPTED_MARKER: ciphertext.decode()}

        # Decrypt with old, re-encrypt with new
        plaintext = old_fernet.decrypt(data[ENCRYPTED_MARKER].encode())
        ciphertext = new_fernet.encrypt(plaintext)
        return {ENCRYPTED_MARKER: ciphertext.decode()}

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key."""
        return Fernet.generate_key().decode()


def _fernet_from_settings() -> Fernet | None:
    """Build a Fernet from the configured ``FERNET_KEY``.

    Returns ``None`` if no key is configured. Keeping this lazy avoids
    crashing module import in unit tests that don't touch encryption at all
    while still failing loudly the moment we actually need to encrypt.
    """
    from app.config import settings

    if not settings.FERNET_KEY:
        return None
    key = settings.FERNET_KEY
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_bytes(plaintext: bytes) -> bytes:
    """Encrypt raw bytes (e.g. a webhook signing secret) at rest.

    Used by Phase 60 F14 to persist webhook signing material that has to be
    recoverable at dispatch time — unlike connection credentials we cannot
    store only a hash because receivers need the raw key.

    Raises ``ValueError`` if no ``FERNET_KEY`` is configured: callers should
    surface this as a 500 rather than silently storing plaintext.
    """
    fernet = _fernet_from_settings()
    if fernet is None:
        raise ValueError("FERNET_KEY is required to encrypt webhook secrets")
    return fernet.encrypt(plaintext)


def decrypt_bytes(ciphertext: bytes) -> bytes:
    """Inverse of :func:`encrypt_bytes`."""
    fernet = _fernet_from_settings()
    if fernet is None:
        raise ValueError("FERNET_KEY is required to decrypt webhook secrets")
    return fernet.decrypt(ciphertext)
