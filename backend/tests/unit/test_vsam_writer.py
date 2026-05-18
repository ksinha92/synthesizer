"""Unit tests for VSAMWriter — golden-byte fixtures."""

from __future__ import annotations

import pytest

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.vsam_writer import VSAMWriter


# ── Schema builders ────────────────────────────────────────────────────

def _build_reference_schema(
    file_format: FileFormat = FileFormat.VSAM_FIXED,
    encoding: str = "ebcdic_cp037",
) -> FileSchemaDefinition:
    """Five-field record covering every renderer branch.

    Layout (byte_length):
      greeting    PIC X(5)              5
      id          PIC 9(5)              5
      signed_id   PIC S9(5)             5  (overpunch)
      bal_comp    PIC S9(5)   COMP      4
      bal_comp3   PIC S9(7)V99 COMP-3   5  (9 digits + sign = 10 nibbles)
      filler      PIC X(3)              3   (filler)
    Total = 27 bytes.
    """
    return FileSchemaDefinition(
        name="ref",
        fields=[
            FileFieldDefinition(name="greeting", data_type="alphanumeric", length=5, byte_length=5, start_position=0),
            FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=5),
            FileFieldDefinition(
                name="signed_id", data_type="numeric", length=5, byte_length=5,
                start_position=10, signed=True,
            ),
            FileFieldDefinition(
                name="bal_comp", data_type="numeric", length=5, byte_length=4,
                start_position=15, signed=True, comp_type="comp",
            ),
            FileFieldDefinition(
                name="bal_comp3", data_type="decimal", length=9, byte_length=5,
                start_position=19, decimal_places=2, signed=True, comp_type="comp_3",
            ),
            FileFieldDefinition(
                name="_filler_1", data_type="alphanumeric", length=3, byte_length=3,
                start_position=24, is_filler=True,
            ),
        ],
        file_format=file_format.value,
        encoding=encoding,
        record_length=27,
        metadata={"implied_decimal": True},
    )


# ── Fixed-format golden fixtures (CP037) ───────────────────────────────

def test_vsam_fixed_alphanumeric_cp037(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(name="greeting", data_type="alphanumeric", length=5, byte_length=5, start_position=0)],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp037",
        record_length=5,
    )
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, [{"greeting": "HELLO"}], out)
    assert out.read_bytes() == b"\xc8\xc5\xd3\xd3\xd6"


def test_vsam_fixed_unsigned_numeric_cp037(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=0)],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp037",
        record_length=5,
    )
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, [{"id": 12345}], out)
    assert out.read_bytes() == b"\xf1\xf2\xf3\xf4\xf5"


def test_vsam_fixed_signed_numeric_overpunch_cp037(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(name="amount", data_type="numeric", length=5, byte_length=5, start_position=0, signed=True)],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp037",
        record_length=5,
    )
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, [{"amount": -123}], out)
    # "00123" → '0','0','1','2','L' (negative 3 overpunch) → f0 f0 f1 f2 d3
    assert out.read_bytes() == b"\xf0\xf0\xf1\xf2\xd3"


def test_vsam_fixed_comp_signed_cp037(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(
            name="amount", data_type="numeric", length=5, byte_length=4,
            start_position=0, signed=True, comp_type="comp",
        )],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp037",
        record_length=4,
    )
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, [{"amount": -1}], out)
    assert out.read_bytes() == b"\xff\xff\xff\xff"


def test_vsam_fixed_comp3_decimal_cp037(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(
            name="balance", data_type="decimal", length=9, byte_length=5,
            start_position=0, decimal_places=2, signed=True, comp_type="comp_3",
        )],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp037",
        record_length=5,
        metadata={"implied_decimal": True},
    )
    out = tmp_path / "t.vsam"
    # 99.5 → 9950 (scaled by 10**2) → 5 bytes COMP-3 with +sign
    VSAMWriter().write(schema, [{"balance": 99.5}], out)
    assert out.read_bytes() == b"\x00\x00\x09\x95\x0c"


def test_vsam_fixed_filler_padded_with_ebcdic_space(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(
            name="_filler_1", data_type="alphanumeric", length=4, byte_length=4,
            start_position=0, is_filler=True,
        )],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp037",
        record_length=4,
    )
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, [{}], out)
    assert out.read_bytes() == b"\x40\x40\x40\x40"


def test_vsam_fixed_redefines_skipped_on_emit(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="code", data_type="alphanumeric", length=4, byte_length=4, start_position=0),
            FileFieldDefinition(
                name="code_redef", data_type="alphanumeric", length=4, byte_length=4,
                start_position=0, redefines="code",
            ),
        ],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp037",
        record_length=4,
    )
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, [{"code": "ABCD", "code_redef": "ZZZZ"}], out)
    # A=0xC1 B=0xC2 C=0xC3 D=0xC4
    assert out.read_bytes() == b"\xc1\xc2\xc3\xc4"


def test_vsam_fixed_cp1140_alphanumeric_matches_cp037_for_letters(tmp_path):
    """CP037 and CP1140 differ only at the Euro sign; ASCII letters share bytes."""
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(name="greeting", data_type="alphanumeric", length=5, byte_length=5, start_position=0)],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp1140",
        record_length=5,
    )
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, [{"greeting": "HELLO"}], out)
    assert out.read_bytes() == b"\xc8\xc5\xd3\xd3\xd6"


# ── Variable-format RDW fixtures ───────────────────────────────────────

def test_vsam_variable_rdw_prefix(tmp_path):
    schema = _build_reference_schema(file_format=FileFormat.VSAM_VARIABLE)
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, [{
        "greeting": "HELLO",
        "id": 1,
        "signed_id": -1,
        "bal_comp": -1,
        "bal_comp3": 9.95,
    }], out)
    data = out.read_bytes()
    # record_length 27 → RDW length = 31 = 0x001f
    assert data[:4] == b"\x00\x1f\x00\x00", data[:4].hex()
    assert len(data) == 31  # RDW(4) + record(27)


def test_vsam_variable_multi_record_total_bytes(tmp_path):
    schema = _build_reference_schema(file_format=FileFormat.VSAM_VARIABLE)
    rows = [{
        "greeting": "HELLO",
        "id": i,
        "signed_id": i,
        "bal_comp": i,
        "bal_comp3": 1.0,
    } for i in range(3)]
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, rows, out)
    # 3 × (record_length 27 + RDW 4) = 93 bytes
    assert len(out.read_bytes()) == 93


# ── Validation rejections ──────────────────────────────────────────────

def test_vsam_rejects_ascii_encoding(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=0)],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ascii",
        record_length=5,
    )
    out = tmp_path / "t.vsam"
    with pytest.raises(ValueError, match="rejects encoding"):
        VSAMWriter().write(schema, [{"id": 1}], out)
    assert not out.exists()


def test_vsam_rejects_non_vsam_format(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=0)],
        file_format=FileFormat.CSV.value,
        encoding="ebcdic_cp037",
        record_length=5,
    )
    out = tmp_path / "t.vsam"
    with pytest.raises(ValueError, match="rejects file_format"):
        VSAMWriter().write(schema, [{"id": 1}], out)


def test_vsam_atomic_no_partial_on_exception(tmp_path, monkeypatch):
    schema = _build_reference_schema()
    rows = [{
        "greeting": "HELLO",
        "id": i,
        "signed_id": i,
        "bal_comp": i,
        "bal_comp3": 1.0,
    } for i in range(3)]

    from app.infrastructure.writers import vsam_writer as vsam_module

    original = vsam_module.VSAMWriter._render_field
    counter = {"n": 0}

    def failing(self, field, value, encoding, implied_decimal):
        counter["n"] += 1
        if counter["n"] >= 8:  # mid-second-row
            raise RuntimeError("simulated mid-write failure")
        return original(self, field, value, encoding, implied_decimal)

    monkeypatch.setattr(vsam_module.VSAMWriter, "_render_field", failing)

    out = tmp_path / "t.vsam"
    with pytest.raises(RuntimeError, match="simulated"):
        VSAMWriter().write(schema, rows, out)
    assert not out.exists()
    assert list(tmp_path.glob(".t.vsam.tmp.*")) == []
