"""Unit tests for FixedWidthWriter — byte-exact assertions + edge cases."""

from __future__ import annotations

import pytest

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.fixed_width_writer import FixedWidthWriter


def _basic_schema(implied_decimal: bool = False) -> FileSchemaDefinition:
    return FileSchemaDefinition(
        name="positions",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=0),
            FileFieldDefinition(name="name", data_type="alphanumeric", length=10, byte_length=10, start_position=5),
            FileFieldDefinition(name="price", data_type="decimal", length=8, byte_length=8, start_position=15, decimal_places=2),
            FileFieldDefinition(name="_filler_1", data_type="alphanumeric", length=2, byte_length=2, start_position=23, is_filler=True),
        ],
        file_format=FileFormat.FIXED_WIDTH.value,
        encoding="ascii",
        record_length=25,
        metadata={"implied_decimal": implied_decimal},
    )


def test_fixed_width_record_length_exact(tmp_path):
    schema = _basic_schema()
    rows = [
        {"id": 1, "name": "Alice", "price": 99.5},
        {"id": 2, "name": "Bob", "price": 0.0},
    ]
    out = tmp_path / "p.txt"
    FixedWidthWriter().write(schema, rows, out)
    data = out.read_bytes()
    # 25 bytes record + 1 byte newline terminator, ×2 records
    assert len(data) == 52, data


def test_fixed_width_numeric_zero_padded(tmp_path):
    schema = _basic_schema()
    rows = [{"id": 1, "name": "X", "price": 1.0}]
    out = tmp_path / "p.txt"
    FixedWidthWriter().write(schema, rows, out)
    rec0 = out.read_bytes()[:25]
    assert rec0[0:5] == b"00001"


def test_fixed_width_alphanumeric_space_padded(tmp_path):
    schema = _basic_schema()
    rows = [{"id": 1, "name": "AB", "price": 1.0}]
    out = tmp_path / "p.txt"
    FixedWidthWriter().write(schema, rows, out)
    rec0 = out.read_bytes()[:25]
    assert rec0[5:15] == b"AB        "


def test_fixed_width_decimal_default_with_dot(tmp_path):
    schema = _basic_schema(implied_decimal=False)
    rows = [{"id": 1, "name": "X", "price": 99.5}]
    out = tmp_path / "p.txt"
    FixedWidthWriter().write(schema, rows, out)
    rec0 = out.read_bytes()[:25]
    assert rec0[15:23] == b"00099.50"


def test_fixed_width_implied_decimal_no_dot(tmp_path):
    schema = _basic_schema(implied_decimal=True)
    rows = [{"id": 1, "name": "X", "price": 99.5}]
    out = tmp_path / "p.txt"
    FixedWidthWriter().write(schema, rows, out)
    rec0 = out.read_bytes()[:25]
    assert rec0[15:23] == b"00009950"


def test_fixed_width_filler_padded_with_pad_char(tmp_path):
    schema = _basic_schema()
    rows = [{"id": 1, "name": "X", "price": 1.0}]
    out = tmp_path / "p.txt"
    FixedWidthWriter().write(schema, rows, out)
    rec0 = out.read_bytes()[:25]
    assert rec0[23:25] == b"  "


def test_fixed_width_redefines_not_double_written(tmp_path):
    """REDEFINES field shares position with target; target's value occupies the bytes."""
    schema = FileSchemaDefinition(
        name="redef",
        fields=[
            FileFieldDefinition(name="code", data_type="alphanumeric", length=4, byte_length=4, start_position=0),
            FileFieldDefinition(
                name="code_redef",
                data_type="alphanumeric",
                length=4,
                byte_length=4,
                start_position=0,
                redefines="code",
            ),
        ],
        file_format=FileFormat.FIXED_WIDTH.value,
        encoding="ascii",
        record_length=4,
    )
    rows = [{"code": "ABCD", "code_redef": "ZZZZ"}]
    out = tmp_path / "p.txt"
    FixedWidthWriter().write(schema, rows, out)
    rec0 = out.read_bytes()[:4]
    # Only the target's value should be present; REDEFINES is skipped on emit.
    assert rec0 == b"ABCD"


def test_fixed_width_rejects_position_overlap(tmp_path):
    schema = FileSchemaDefinition(
        name="bad",
        fields=[
            FileFieldDefinition(name="a", data_type="numeric", length=4, byte_length=4, start_position=0),
            FileFieldDefinition(name="b", data_type="numeric", length=4, byte_length=4, start_position=2),
        ],
        file_format=FileFormat.FIXED_WIDTH.value,
        encoding="ascii",
        record_length=6,
    )
    out = tmp_path / "p.txt"
    with pytest.raises(ValueError, match="Schema validation failed"):
        FixedWidthWriter().write(schema, [{"a": 1, "b": 2}], out)
    assert not out.exists()


def test_fixed_width_rejects_signed_numeric(tmp_path):
    """Signed display numerics use COBOL overpunch — defer to VSAMWriter."""
    schema = FileSchemaDefinition(
        name="signed",
        fields=[
            FileFieldDefinition(
                name="amount", data_type="numeric", length=5, byte_length=5,
                start_position=0, signed=True,
            ),
        ],
        file_format=FileFormat.FIXED_WIDTH.value,
        encoding="ascii",
        record_length=5,
    )
    out = tmp_path / "p.txt"
    with pytest.raises(ValueError, match="signed.*VSAMWriter"):
        FixedWidthWriter().write(schema, [{"amount": 42}], out)
    assert not out.exists()


def test_fixed_width_rejects_signed_decimal(tmp_path):
    """Signed display decimals — same deferral as signed numerics."""
    schema = FileSchemaDefinition(
        name="signed_dec",
        fields=[
            FileFieldDefinition(
                name="balance", data_type="decimal", length=9, byte_length=9,
                start_position=0, decimal_places=2, signed=True,
            ),
        ],
        file_format=FileFormat.FIXED_WIDTH.value,
        encoding="ascii",
        record_length=9,
        metadata={"implied_decimal": True},
    )
    out = tmp_path / "p.txt"
    with pytest.raises(ValueError, match="signed.*VSAMWriter"):
        FixedWidthWriter().write(schema, [{"balance": 99.5}], out)
    assert not out.exists()


def test_fixed_width_rejects_packed_decimal(tmp_path):
    """COMP-3 packed-decimal fields belong to VSAMWriter."""
    schema = FileSchemaDefinition(
        name="packed",
        fields=[
            FileFieldDefinition(
                name="amount", data_type="packed_decimal", length=9, byte_length=5,
                start_position=0, decimal_places=2,
            ),
        ],
        file_format=FileFormat.FIXED_WIDTH.value,
        encoding="ascii",
        record_length=5,
    )
    out = tmp_path / "p.txt"
    with pytest.raises(ValueError, match="VSAMWriter"):
        FixedWidthWriter().write(schema, [{"amount": 99.5}], out)


def test_fixed_width_copybook_unsigned_decimal_round_trip(tmp_path):
    """A schema produced by CopybookParser must render correctly through FixedWidthWriter
    for unsigned decimal fields — implied decimal point, zero-padded digits, no '.'.
    """
    from app.infrastructure.parsers.copybook_parser import CopybookParser
    from app.domain.synthetic.value_objects import FileFormat as FF

    copybook = """
       01  POLICY-RECORD.
           05  POL-ID            PIC 9(5).
           05  POL-PREMIUM       PIC 9(7)V99.
"""
    schema = CopybookParser().parse(
        copybook,
        name="policy",
        default_format=FF.FIXED_WIDTH,
    )

    assert schema.metadata.get("implied_decimal") is True
    # POL-ID = 5 bytes, POL-PREMIUM = 9 bytes (7 int + 2 dec, all digits)
    assert schema.compute_record_length() == 14

    out = tmp_path / "policy.txt"
    FixedWidthWriter().write(schema, [{"POL-ID": 42, "POL-PREMIUM": 1234.5}], out)
    rec0 = out.read_bytes()[:14]

    assert rec0[0:5] == b"00042", rec0[0:5]
    # 1234.5 with 2 decimal places, implied → "1234.50" → digits 123450, zero-padded to 9
    assert rec0[5:14] == b"000123450", rec0[5:14]


def test_fixed_width_atomic_no_partial_on_exception(tmp_path, monkeypatch):
    schema = _basic_schema()
    rows = [
        {"id": 1, "name": "Alice", "price": 1.0},
        {"id": 2, "name": "Bob", "price": 2.0},
    ]
    out = tmp_path / "p.txt"

    from app.infrastructure.writers import fixed_width_writer as fw_module

    original = fw_module.FixedWidthWriter._render_field
    counter = {"n": 0}

    def failing(self, field, value, implied_decimal):
        counter["n"] += 1
        # Each row renders 3 non-filler + 1 filler fields = 4 calls/row.
        # Fail partway through the second row.
        if counter["n"] >= 6:
            raise RuntimeError("simulated mid-write failure")
        return original(self, field, value, implied_decimal)

    monkeypatch.setattr(fw_module.FixedWidthWriter, "_render_field", failing)

    with pytest.raises(RuntimeError, match="simulated"):
        FixedWidthWriter().write(schema, rows, out)

    assert not out.exists(), "output_path must not exist after mid-write exception"
    leftovers = list(tmp_path.glob(".p.txt.tmp.*"))
    assert leftovers == [], f"tmp file not cleaned up: {leftovers}"
