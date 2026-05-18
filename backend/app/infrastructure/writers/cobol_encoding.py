"""COBOL value encoders for VSAM output.

Pure functions, no I/O. Each encoder returns bytes whose length matches the
schema's `byte_length` for the corresponding field shape:

  - encode_comp3(value, digits, signed)         → ceil((digits + 1) / 2) bytes
  - encode_comp(value, digits, signed)          → 2 / 4 / 8 bytes by digit count
  - encode_display_signed(value, digits, ...)   → digits bytes (sign overpunched on last)
"""

from __future__ import annotations

import math

from app.infrastructure.writers import ebcdic_codec


# Overpunch maps — last-digit substitution by sign.
# Keys are digit characters; values are the ASCII characters whose EBCDIC
# encoding carries the appropriate digit + sign combination.
_POSITIVE_OVERPUNCH = {
    "0": "{",
    "1": "A", "2": "B", "3": "C", "4": "D", "5": "E",
    "6": "F", "7": "G", "8": "H", "9": "I",
}
_NEGATIVE_OVERPUNCH = {
    "0": "}",
    "1": "J", "2": "K", "3": "L", "4": "M", "5": "N",
    "6": "O", "7": "P", "8": "Q", "9": "R",
}


def encode_comp3(value: int, digits: int, signed: bool) -> bytes:
    """Pack an integer as COMP-3 packed decimal.

    Layout: each digit is one nibble, followed by a sign nibble.
      - signed positive → 0xC
      - signed negative → 0xD
      - unsigned        → 0xF
    Total nibbles = digits + 1; bytes = ceil((digits + 1) / 2).
    If the total nibble count is odd, a leading zero nibble is prepended
    so the digits left-align in the byte sequence.
    """
    if not signed and value < 0:
        raise OverflowError(
            f"Unsigned COMP-3 cannot encode negative value {value}"
        )

    abs_str = str(abs(value))
    if len(abs_str) > digits:
        raise OverflowError(
            f"Value {value} has {len(abs_str)} digits but field declares {digits}"
        )
    padded = abs_str.rjust(digits, "0")

    if not signed:
        sign_nibble = 0xF
    elif value < 0:
        sign_nibble = 0xD
    else:
        sign_nibble = 0xC

    # Build nibble list: digits then sign.
    nibbles: list[int] = [int(d) for d in padded] + [sign_nibble]

    # If odd nibble count, pad leading zero so we pack two-per-byte cleanly.
    if len(nibbles) % 2 == 1:
        nibbles.insert(0, 0)

    out = bytearray()
    for i in range(0, len(nibbles), 2):
        high = nibbles[i] & 0xF
        low = nibbles[i + 1] & 0xF
        out.append((high << 4) | low)

    expected_bytes = math.ceil((digits + 1) / 2)
    if len(out) != expected_bytes:  # pragma: no cover - guarded by algorithm
        raise AssertionError(
            f"encode_comp3 produced {len(out)} bytes, expected {expected_bytes}"
        )
    return bytes(out)


def encode_comp(value: int, digits: int, signed: bool) -> bytes:
    """Encode an integer as COMP big-endian binary.

    Byte length is determined by digit count:
      1-4 → 2 bytes, 5-9 → 4 bytes, 10-18 → 8 bytes.
    Signed values use two's complement.
    """
    if not signed and value < 0:
        raise OverflowError(
            f"Unsigned COMP cannot encode negative value {value}"
        )
    if digits <= 4:
        byte_length = 2
    elif digits <= 9:
        byte_length = 4
    elif digits <= 18:
        byte_length = 8
    else:
        raise ValueError(f"COMP digit count {digits} exceeds 18")

    # int.to_bytes will raise OverflowError if the value doesn't fit.
    return value.to_bytes(byte_length, "big", signed=signed)


def encode_display_signed(value: int, digits: int, encoding: str) -> bytes:
    """Encode a signed integer as display-numeric with EBCDIC overpunch.

    The first `digits-1` characters are plain EBCDIC '0'..'9' digits. The
    last byte fuses the last digit with the sign per the overpunch map:
      +0..+9 → '{', 'A'..'I'
      -0..-9 → '}', 'J'..'R'
    """
    abs_str = str(abs(value))
    if len(abs_str) > digits:
        raise OverflowError(
            f"Value {value} has {len(abs_str)} digits but field declares {digits}"
        )
    padded = abs_str.rjust(digits, "0")

    head_digits = padded[:-1]
    last_digit = padded[-1]
    overpunch_map = _NEGATIVE_OVERPUNCH if value < 0 else _POSITIVE_OVERPUNCH
    last_char = overpunch_map[last_digit]

    head_bytes = ebcdic_codec.encode(head_digits, encoding)
    tail_byte = ebcdic_codec.encode(last_char, encoding)
    out = head_bytes + tail_byte
    if len(out) != digits:  # pragma: no cover
        raise AssertionError(
            f"encode_display_signed produced {len(out)} bytes, expected {digits}"
        )
    return out
