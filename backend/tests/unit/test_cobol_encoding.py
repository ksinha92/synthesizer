"""Unit tests for COBOL encoders — golden-byte assertions."""

from __future__ import annotations

import math

import pytest

from app.infrastructure.writers.cobol_encoding import (
    encode_comp,
    encode_comp3,
    encode_display_signed,
)


# ── COMP-3 ─────────────────────────────────────────────────────────────

def test_comp3_unsigned_zero():
    assert encode_comp3(0, 3, False) == b"\x00\x0f"


def test_comp3_unsigned_123():
    assert encode_comp3(123, 3, False) == b"\x12\x3f"


def test_comp3_signed_positive_123():
    assert encode_comp3(123, 3, True) == b"\x12\x3c"


def test_comp3_signed_negative_123():
    assert encode_comp3(-123, 3, True) == b"\x12\x3d"


def test_comp3_9_digits_signed():
    # 9 digits + sign = 10 nibbles = 5 bytes
    # value 9950 padded → "000009950" + 0xC nibble → 00 00 09 95 0c
    assert encode_comp3(9950, 9, True) == b"\x00\x00\x09\x95\x0c"


def test_comp3_5_digits_unsigned():
    # 5 digits + sign = 6 nibbles (even) → 3 bytes, no leading pad nibble.
    # 99999 → 9,9,9,9,9,F → 0x99, 0x99, 0x9F
    assert encode_comp3(99999, 5, False) == b"\x99\x99\x9f"


def test_comp3_unsigned_rejects_negative():
    with pytest.raises(OverflowError):
        encode_comp3(-1, 5, False)


def test_comp3_overflow_too_many_digits():
    with pytest.raises(OverflowError):
        encode_comp3(123456, 5, False)


def test_comp3_byte_length_formula():
    for d in range(1, 19):
        out = encode_comp3(0, d, False)
        assert len(out) == math.ceil((d + 1) / 2)


# ── COMP (big-endian binary) ───────────────────────────────────────────

def test_comp_2byte_negative_one():
    assert encode_comp(-1, 3, True) == b"\xff\xff"


def test_comp_4byte_minus_one():
    assert encode_comp(-1, 5, True) == b"\xff\xff\xff\xff"


def test_comp_8byte_round_trip():
    value = 10 ** 14
    out = encode_comp(value, 15, True)
    assert len(out) == 8
    assert int.from_bytes(out, "big", signed=True) == value


def test_comp_4byte_overflow():
    with pytest.raises(OverflowError):
        encode_comp(2 ** 31, 9, True)


def test_comp_unsigned_rejects_negative():
    with pytest.raises(OverflowError):
        encode_comp(-1, 5, False)


def test_comp_unsigned_2byte():
    assert encode_comp(1, 3, False) == (1).to_bytes(2, "big")


# ── Display-signed overpunch ───────────────────────────────────────────

def test_display_signed_positive_zero_cp037():
    # +0 → trailing '{' = EBCDIC 0xC0
    out = encode_display_signed(0, 3, "ebcdic_cp037")
    assert out[-1:] == b"\xc0"


def test_display_signed_negative_3_digits_cp037():
    # -123 padded to 5 digits: "00123" with last digit 3 overpunched negative → 'L'
    # EBCDIC '0'=0xF0, '1'=0xF1, '2'=0xF2, 'L'=0xD3
    out = encode_display_signed(-123, 5, "ebcdic_cp037")
    assert out == b"\xf0\xf0\xf1\xf2\xd3"


def test_display_signed_overflow():
    with pytest.raises(OverflowError):
        encode_display_signed(123456, 5, "ebcdic_cp037")


def test_display_signed_positive_9_overpunch():
    # +9 in 1 digit → 'I' = EBCDIC 0xC9
    assert encode_display_signed(9, 1, "ebcdic_cp037") == b"\xc9"


def test_display_signed_negative_9_overpunch():
    # -9 in 1 digit → 'R' = EBCDIC 0xD9
    assert encode_display_signed(-9, 1, "ebcdic_cp037") == b"\xd9"
