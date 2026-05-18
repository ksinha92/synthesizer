"""Unit tests for ColumnarWriter — Parquet + ORC round-trip."""

from __future__ import annotations

import decimal

import pytest

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.columnar_writer import ColumnarWriter


def _schema(file_format: FileFormat = FileFormat.PARQUET) -> FileSchemaDefinition:
    return FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=5, byte_length=5, start_position=0),
            FileFieldDefinition(name="name", data_type="alphanumeric", length=10, byte_length=10, start_position=5),
            FileFieldDefinition(
                name="balance", data_type="decimal", length=10, byte_length=10,
                start_position=15, decimal_places=2,
            ),
        ],
        file_format=file_format.value,
    )


def test_parquet_round_trip(tmp_path):
    import pyarrow.parquet as pq

    schema = _schema()
    rows = [
        {"id": 1, "name": "Alice", "balance": 100.50},
        {"id": 2, "name": "Bob", "balance": None},
    ]
    out = tmp_path / "t.parquet"
    ColumnarWriter().write(schema, rows, out)
    table = pq.read_table(out)
    assert table.column_names == ["id", "name", "balance"]
    py = table.to_pydict()
    assert py["id"] == [1, 2]
    assert py["name"] == ["Alice", "Bob"]
    assert py["balance"][0] == decimal.Decimal("100.50")
    assert py["balance"][1] is None


def test_orc_round_trip(tmp_path):
    import pyarrow.orc as orc

    schema = _schema(file_format=FileFormat.ORC)
    rows = [{"id": 1, "name": "Alice", "balance": 10.25}]
    out = tmp_path / "t.orc"
    ColumnarWriter().write(schema, rows, out)
    table = orc.read_table(out)
    assert table.column_names == ["id", "name", "balance"]
    py = table.to_pydict()
    assert py["id"] == [1]
    assert py["balance"][0] == decimal.Decimal("10.25")


def test_parquet_decimal_precision_scale(tmp_path):
    import pyarrow.parquet as pq
    import pyarrow as pa

    schema = _schema()
    out = tmp_path / "t.parquet"
    ColumnarWriter().write(schema, [{"id": 1, "name": "x", "balance": 1.0}], out)
    table = pq.read_table(out)
    bal_type = table.schema.field("balance").type
    assert pa.types.is_decimal(bal_type)
    assert bal_type.precision == 10
    assert bal_type.scale == 2


def test_parquet_int32_for_short_comp(tmp_path):
    import pyarrow.parquet as pq
    import pyarrow as pa

    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(
                name="small_int", data_type="numeric", length=4, byte_length=2,
                start_position=0, comp_type="comp",
            ),
        ],
        file_format=FileFormat.PARQUET.value,
    )
    out = tmp_path / "t.parquet"
    ColumnarWriter().write(schema, [{"small_int": 42}], out)
    table = pq.read_table(out)
    assert pa.types.is_int32(table.schema.field("small_int").type)


def test_filler_fields_excluded(tmp_path):
    import pyarrow.parquet as pq

    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(name="id", data_type="numeric", length=3, byte_length=3, start_position=0),
            FileFieldDefinition(
                name="_filler_1", data_type="alphanumeric", length=4, byte_length=4,
                start_position=3, is_filler=True,
            ),
            FileFieldDefinition(name="code", data_type="alphanumeric", length=2, byte_length=2, start_position=7),
        ],
        file_format=FileFormat.PARQUET.value,
    )
    out = tmp_path / "t.parquet"
    ColumnarWriter().write(schema, [{"id": 1, "code": "AB"}], out)
    table = pq.read_table(out)
    assert table.column_names == ["id", "code"]


def test_columnar_rejects_binary_field(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(
                name="raw", data_type="binary", length=4, byte_length=4,
                start_position=0,
            ),
        ],
        file_format=FileFormat.PARQUET.value,
    )
    out = tmp_path / "t.parquet"
    with pytest.raises(ValueError, match="binary fields"):
        ColumnarWriter().write(schema, [{"raw": b"\x00\x00\x00\x00"}], out)


def test_columnar_rejects_packed_decimal_field(tmp_path):
    schema = FileSchemaDefinition(
        name="t",
        fields=[
            FileFieldDefinition(
                name="bal", data_type="packed_decimal", length=5, byte_length=3,
                start_position=0, decimal_places=2,
            ),
        ],
        file_format=FileFormat.PARQUET.value,
    )
    out = tmp_path / "t.parquet"
    with pytest.raises(ValueError, match="packed_decimal"):
        ColumnarWriter().write(schema, [{"bal": 1.0}], out)


def test_columnar_compression_setting_honored(tmp_path):
    import pyarrow.parquet as pq

    schema = _schema()
    rows = [{"id": 1, "name": "x", "balance": 1.0}]

    out = tmp_path / "snappy.parquet"
    ColumnarWriter(compression="snappy").write(schema, rows, out)
    md = pq.read_metadata(out)
    # row_group(0).column(0) has codec attribute
    codec = md.row_group(0).column(0).compression
    assert codec.lower() == "snappy"

    out2 = tmp_path / "gzip.parquet"
    ColumnarWriter(compression="gzip").write(schema, rows, out2)
    md2 = pq.read_metadata(out2)
    assert md2.row_group(0).column(0).compression.lower() == "gzip"


def test_columnar_atomic_no_partial_on_exception(tmp_path, monkeypatch):
    import pyarrow.parquet as pq

    schema = _schema()
    out = tmp_path / "t.parquet"

    def boom(*args, **kwargs):
        raise RuntimeError("simulated parquet failure")

    monkeypatch.setattr(pq, "write_table", boom)

    with pytest.raises(RuntimeError, match="simulated"):
        ColumnarWriter().write(schema, [{"id": 1, "name": "x", "balance": 1.0}], out)
    assert not out.exists()
    assert list(tmp_path.glob(".t.parquet.tmp.*")) == []
