"""Round-trip tests for sample file parsers against Phase 44 writers."""

from __future__ import annotations

import pandas as pd
import pytest

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.parsers.sample_file_parser import (
    parse,
    parse_columnar,
    parse_csv,
    parse_fixed_width,
    parse_vsam,
)
from app.infrastructure.writers.columnar_writer import ColumnarWriter
from app.infrastructure.writers.csv_writer import CSVWriter
from app.infrastructure.writers.fixed_width_writer import FixedWidthWriter
from app.infrastructure.writers.vsam_writer import VSAMWriter


def _csv_schema() -> FileSchemaDefinition:
    return FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=4, byte_length=4, start_position=0),
            FileFieldDefinition(name="name", data_type="alphanumeric", length=10, byte_length=10, start_position=4),
        ],
        file_format=FileFormat.CSV.value,
    )


def test_parse_csv_round_trip(tmp_path):
    schema = _csv_schema()
    rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    out = tmp_path / "t.csv"
    CSVWriter(line_terminator="\n").write(schema, rows, out)
    df = parse_csv(out, schema)
    assert df["id"].tolist() == [1, 2]
    assert df["name"].tolist() == ["Alice", "Bob"]


def test_parse_csv_rejects_column_mismatch(tmp_path):
    out = tmp_path / "t.csv"
    out.write_text("id,extra\n1,X\n")
    with pytest.raises(ValueError, match="do not match schema"):
        parse_csv(out, _csv_schema())


def test_parse_fixed_width_implied_decimal(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=4, byte_length=4, start_position=0),
            FileFieldDefinition(
                name="price", data_type="decimal", length=6, byte_length=6,
                start_position=4, decimal_places=2,
            ),
        ],
        file_format=FileFormat.FIXED_WIDTH.value,
        encoding="ascii",
        record_length=10,
        metadata={"implied_decimal": True},
    )
    rows = [{"id": 1, "price": 99.5}, {"id": 2, "price": 10.0}]
    out = tmp_path / "t.txt"
    FixedWidthWriter().write(schema, rows, out)
    df = parse_fixed_width(out, schema)
    assert df["id"].tolist() == [1, 2]
    assert df["price"].tolist() == [99.5, 10.0]


def test_parse_vsam_fixed_round_trip(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="greeting", data_type="alphanumeric", length=5, byte_length=5, start_position=0),
            FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=5),
            FileFieldDefinition(
                name="amount", data_type="numeric", length=5, byte_length=5,
                start_position=10, signed=True,
            ),
            FileFieldDefinition(
                name="bal", data_type="decimal", length=9, byte_length=5,
                start_position=15, decimal_places=2, signed=True, comp_type="comp_3",
            ),
        ],
        file_format=FileFormat.VSAM_FIXED.value,
        encoding="ebcdic_cp037",
        record_length=20,
        metadata={"implied_decimal": True},
    )
    rows = [
        {"greeting": "HELLO", "id": 12345, "amount": -123, "bal": 99.5},
        {"greeting": "WORLD", "id": 1, "amount": 7, "bal": -1.25},
    ]
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, rows, out)
    df = parse_vsam(out, schema)
    assert df["greeting"].tolist() == ["HELLO", "WORLD"]
    assert df["id"].tolist() == [12345, 1]
    assert df["amount"].tolist() == [-123, 7]
    assert df["bal"].tolist() == [99.5, -1.25]


def test_parse_vsam_variable_round_trip(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="greeting", data_type="alphanumeric", length=5, byte_length=5, start_position=0),
            FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=5),
        ],
        file_format=FileFormat.VSAM_VARIABLE.value,
        encoding="ebcdic_cp037",
        record_length=10,
    )
    rows = [{"greeting": "HELLO", "id": 1}, {"greeting": "WORLD", "id": 2}]
    out = tmp_path / "t.vsam"
    VSAMWriter().write(schema, rows, out)
    df = parse_vsam(out, schema)
    assert df["greeting"].tolist() == ["HELLO", "WORLD"]
    assert df["id"].tolist() == [1, 2]


def test_parse_columnar_parquet_round_trip(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=0),
            FileFieldDefinition(name="name", data_type="alphanumeric", length=10, byte_length=10, start_position=5),
            FileFieldDefinition(
                name="bal", data_type="decimal", length=10, byte_length=10,
                start_position=15, decimal_places=2,
            ),
        ],
        file_format=FileFormat.PARQUET.value,
    )
    rows = [{"id": 1, "name": "Alice", "bal": 100.50}]
    out = tmp_path / "t.parquet"
    ColumnarWriter().write(schema, rows, out)
    df = parse_columnar(out, schema)
    assert df["id"].tolist() == [1]
    assert df["name"].tolist() == ["Alice"]
    assert df["bal"].tolist() == [100.50]


def test_parse_columnar_orc_round_trip(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=0),
        ],
        file_format=FileFormat.ORC.value,
    )
    rows = [{"id": 1}, {"id": 2}]
    out = tmp_path / "t.orc"
    ColumnarWriter().write(schema, rows, out)
    df = parse_columnar(out, schema)
    assert df["id"].tolist() == [1, 2]


def test_parse_dispatcher_routes_by_format(tmp_path):
    schema = _csv_schema()
    rows = [{"id": 1, "name": "Alice"}]
    out = tmp_path / "t.csv"
    CSVWriter(line_terminator="\n").write(schema, rows, out)
    df = parse(out, schema)
    assert isinstance(df, pd.DataFrame)
    assert df["id"].tolist() == [1]


def test_parse_dispatcher_rejects_unknown_format():
    schema = _csv_schema()
    schema.file_format = "unknown"
    with pytest.raises(ValueError, match="No parser"):
        parse("/tmp/whatever", schema)
