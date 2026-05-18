"""EBCDIC codec wrapper.

Thin layer over Python's stdlib `codecs` module. Restricted to the two code
pages VSAMWriter supports: CP037 (US/Canada) and CP1140 (Euro variant).
No third-party `ebcdic` package — stdlib covers both pages.
"""

from __future__ import annotations


EBCDIC_ENCODINGS: dict[str, str] = {
    "ebcdic_cp037": "cp037",
    "ebcdic_cp1140": "cp1140",
}


def to_python_codec(encoding: str) -> str:
    """Map an EncodingType enum value to a stdlib codec name."""
    codec = EBCDIC_ENCODINGS.get(encoding)
    if codec is None:
        raise ValueError(f"Unsupported EBCDIC encoding: {encoding!r}")
    return codec


def encode(text: str, encoding: str) -> bytes:
    """Encode a Python string to the given EBCDIC code page."""
    return text.encode(to_python_codec(encoding))


def space(encoding: str) -> bytes:
    """Single EBCDIC space byte for the given code page."""
    return encode(" ", encoding)


def zero(encoding: str) -> bytes:
    """Single EBCDIC '0' digit byte for the given code page."""
    return encode("0", encoding)
