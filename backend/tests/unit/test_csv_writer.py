"""Unit tests for CSVWriter — round-trip + edge cases."""

from __future__ import annotations

import csv

import pytest

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.csv_writer import CSVWriter


def _basic_schema() -> FileSchemaDefinition:
    return FileSchemaDefinition(
        name="customers",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=4, byte_length=4, start_position=0),
            FileFieldDefinition(name="name", data_type="alphanumeric", length=10, byte_length=10, start_position=4),
            FileFieldDefinition(name="balance", data_type="decimal", length=10, byte_length=10, start_position=14, decimal_places=2),
        ],
        file_format=FileFormat.CSV.value,
        encoding="utf-8",
    )


def test_csv_round_trip_basic(tmp_path):
    schema = _basic_schema()
    rows = [
        {"id": 1, "name": "Alice", "balance": 100.5},
        {"id": 2, "name": "Bob", "balance": 50.25},
    ]
    out = tmp_path / "customers.csv"
    CSVWriter(line_terminator="\n").write(schema, rows, out)

    with open(out, "r", newline="", encoding="utf-8") as f:
        read = list(csv.DictReader(f))

    assert len(read) == 2
    assert read[0] == {"id": "1", "name": "Alice", "balance": "100.50"}
    assert read[1] == {"id": "2", "name": "Bob", "balance": "50.25"}


def test_csv_quotes_special_chars(tmp_path):
    schema = _basic_schema()
    rows = [
        {"id": 1, "name": "B,ob", "balance": 1.0},
        {"id": 2, "name": 'Carol "Q"', "balance": 2.0},
        {"id": 3, "name": "line\nbreak", "balance": 3.0},
    ]
    out = tmp_path / "customers.csv"
    CSVWriter(line_terminator="\n").write(schema, rows, out)

    with open(out, "r", newline="", encoding="utf-8") as f:
        read = list(csv.DictReader(f))

    assert read[0]["name"] == "B,ob"
    assert read[1]["name"] == 'Carol "Q"'
    assert read[2]["name"] == "line\nbreak"


def test_csv_none_serializes_as_empty(tmp_path):
    schema = _basic_schema()
    rows = [{"id": 1, "name": "Alice", "balance": None}]
    out = tmp_path / "x.csv"
    CSVWriter(line_terminator="\n").write(schema, rows, out)

    with open(out, "r", newline="", encoding="utf-8") as f:
        read = list(csv.DictReader(f))
    assert read[0]["balance"] == ""


def test_csv_decimal_places_honored(tmp_path):
    schema = _basic_schema()
    rows = [{"id": 1, "name": "Alice", "balance": 100.0}]
    out = tmp_path / "x.csv"
    CSVWriter(line_terminator="\n").write(schema, rows, out)

    text = out.read_text(encoding="utf-8")
    assert "100.00" in text


def test_csv_filler_fields_skipped(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=3, byte_length=3, start_position=0),
            FileFieldDefinition(name="_filler_1", data_type="alphanumeric", length=2, byte_length=2, start_position=3, is_filler=True),
            FileFieldDefinition(name="code", data_type="alphanumeric", length=4, byte_length=4, start_position=5),
        ],
        file_format=FileFormat.CSV.value,
    )
    rows = [{"id": 1, "code": "AAA"}]
    out = tmp_path / "x.csv"
    CSVWriter(line_terminator="\n").write(schema, rows, out)

    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",") == ["id", "code"]


def test_csv_bom_toggle(tmp_path):
    schema = _basic_schema()
    rows = [{"id": 1, "name": "Alice", "balance": 1.0}]

    out_no_bom = tmp_path / "no_bom.csv"
    CSVWriter(line_terminator="\n", write_bom=False).write(schema, rows, out_no_bom)
    assert out_no_bom.read_bytes()[:3] != b"\xef\xbb\xbf"

    out_bom = tmp_path / "bom.csv"
    CSVWriter(line_terminator="\n", write_bom=True).write(schema, rows, out_bom)
    assert out_bom.read_bytes()[:3] == b"\xef\xbb\xbf"


def test_csv_rejects_invalid_schema(tmp_path):
    schema = FileSchemaDefinition(
        name="dup",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=3, byte_length=3, start_position=0),
            FileFieldDefinition(name="id", data_type="numeric", length=3, byte_length=3, start_position=3),
        ],
        file_format=FileFormat.CSV.value,
    )
    out = tmp_path / "x.csv"
    with pytest.raises(ValueError, match="Schema validation failed"):
        CSVWriter(line_terminator="\n").write(schema, [{"id": 1}], out)
    assert not out.exists()


def test_csv_atomic_no_partial_on_exception(tmp_path, monkeypatch):
    schema = _basic_schema()
    rows = [
        {"id": 1, "name": "Alice", "balance": 1.0},
        {"id": 2, "name": "Bob", "balance": 2.0},
        {"id": 3, "name": "Carol", "balance": 3.0},
    ]
    out = tmp_path / "x.csv"

    # Build a counter-based fail-on-third call using monkeypatch on csv.writer
    call_count = {"n": 0}
    original_csv_writer = csv.writer

    class FailingWriter:
        def __init__(self, real):
            self._real = real

        def writerow(self, row):
            call_count["n"] += 1
            # Headers are row 1; rows are 2,3,4. Fail on row 3 (second data row).
            if call_count["n"] == 3:
                raise RuntimeError("simulated mid-write failure")
            return self._real.writerow(row)

    def factory(*args, **kwargs):
        return FailingWriter(original_csv_writer(*args, **kwargs))

    monkeypatch.setattr(csv, "writer", factory)

    with pytest.raises(RuntimeError, match="simulated"):
        CSVWriter(line_terminator="\n").write(schema, rows, out)

    assert not out.exists(), "output_path must not exist after mid-write exception"
    # And no leftover .tmp.* siblings
    leftovers = list(tmp_path.glob(".x.csv.tmp.*"))
    assert leftovers == [], f"tmp file not cleaned up: {leftovers}"
