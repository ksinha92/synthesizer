"""Masking value objects. No framework dependencies."""

from enum import Enum


class MaskingStrategy(str, Enum):
    HASH = "hash"
    REDACT = "redact"
    FAKER_REPLACE = "faker_replace"
    SHUFFLE = "shuffle"
    NULLIFY = "nullify"
    FPE = "fpe"
    PARTIAL_MASK = "partial_mask"
    # PRESIDIO_REDACT is the free-text equivalent of REDACT — instead of
    # blanking the whole value, it runs Presidio over the string and
    # replaces each detected entity span (PERSON, EMAIL, SSN, etc.) with a
    # typed placeholder like [PERSON]. Intended for narrative columns
    # (notes, claims descriptions) where the surrounding text is non-PII
    # and should stay readable. Falls back to REDACT when Presidio is
    # unavailable in the runtime.
    PRESIDIO_REDACT = "presidio_redact"
