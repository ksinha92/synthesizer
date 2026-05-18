"""Columnar writer — Parquet + ORC via pyarrow.

Pyarrow is imported lazily inside `write()` so the writer module can be
imported (and registered) even when pyarrow is briefly unavailable; the
failure surface is the write call rather than module import.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from app.domain.synthetic.file_schema import (
    FileFieldDefinition,
    FileSchemaDefinition,
)
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.base_writer import BaseFileWriter, write_atomic


_SUPPORTED_FORMATS = {FileFormat.PARQUET.value, FileFormat.ORC.value}


class ColumnarWriter(BaseFileWriter):
    """Emit rows as Parquet or ORC."""

    def __init__(self, compression: str = "snappy") -> None:
        self._compression = compression

    @classmethod
    def supported_formats(cls) -> set[FileFormat]:
        return {FileFormat.PARQUET, FileFormat.ORC}

    def get_extension(self) -> str:
        return "parquet"

    def validate_schema(self, schema: FileSchemaDefinition) -> list[str]:
        errors = list(super().validate_schema(schema))
        if schema.file_format not in _SUPPORTED_FORMATS:
            errors.append(
                f"ColumnarWriter rejects file_format={schema.file_format!r}; "
                f"expected one of {sorted(_SUPPORTED_FORMATS)}"
            )
        for f in schema.fields:
            if f.is_filler:
                continue
            if f.data_type == "binary":
                errors.append(
                    f"Field {f.name!r}: binary fields belong to VSAMWriter, "
                    f"not ColumnarWriter (analytics output is decimal/int/string)"
                )
            if f.data_type == "packed_decimal":
                errors.append(
                    f"Field {f.name!r}: packed_decimal belongs to VSAMWriter, "
                    f"not ColumnarWriter"
                )
            if f.signed and f.data_type in ("numeric", "decimal"):
                # Analytics columnar output uses ordinary int64 / decimal128;
                # signed-display overpunch is mainframe-only and goes through VSAMWriter.
                # We still allow signed numerics here when comp_type == "comp"
                # (binary int with sign), but reject signed display values.
                if f.comp_type != "comp":
                    errors.append(
                        f"Field {f.name!r}: signed display numerics use COBOL overpunch; "
                        f"emit via VSAMWriter, or set comp_type='comp' for binary int signed encoding"
                    )
        return errors

    # ── Arrow type mapping ───────────────────────────────────────────────

    def _map_arrow_type(self, field: FileFieldDefinition):
        import pyarrow as pa

        if field.is_filler:  # pragma: no cover - callers pre-skip
            raise ValueError(f"Filler field {field.name!r} should not be mapped")

        dt = field.data_type
        if dt == "alphanumeric":
            return pa.string()
        if dt == "decimal":
            return pa.decimal128(field.length, field.decimal_places)
        if dt == "numeric":
            if field.decimal_places > 0:
                return pa.decimal128(field.length, field.decimal_places)
            if field.comp_type == "comp" and field.length <= 9:
                return pa.int32()
            return pa.int64()
        if dt == "binary":  # rejected in validate, but handle defensively
            return pa.binary(field.byte_length)
        if dt == "packed_decimal":  # likewise
            return pa.decimal128(field.length, field.decimal_places)
        # Guard rail (not a stub). ColumnarWriter maps every COBOL data_type
        # used in the upstream schema onto an Arrow logical type:
        #   alphanumeric → string, decimal → decimal128(p,s),
        #   numeric → decimal128 / int32 / int64 (based on comp + length),
        #   binary → fixed-size binary, packed_decimal → decimal128.
        # Reaching this branch means the schema introduced a data_type we
        # do not know how to project into Arrow yet — fail loudly so the
        # caller gets a 422 from /file-sets/generate instead of a silently
        # mis-typed Parquet/ORC file.
        raise NotImplementedError(
            f"ColumnarWriter cannot map data_type {dt!r} (field {field.name!r}); "
            f"supported: alphanumeric, numeric, decimal, binary, packed_decimal"
        )

    # ── Build + write ────────────────────────────────────────────────────

    def _coerce_cell(self, field: FileFieldDefinition, value: Any):
        if value is None:
            return None
        if field.data_type == "decimal" or (
            field.data_type in ("numeric", "packed_decimal") and field.decimal_places > 0
        ):
            quant = Decimal(1).scaleb(-field.decimal_places)
            return Decimal(str(value)).quantize(quant)
        if field.data_type == "numeric":
            return int(value)
        if field.data_type == "alphanumeric":
            return str(value)
        return value

    def _build_arrow_table(self, schema: FileSchemaDefinition, rows: list[dict]):
        import pyarrow as pa

        emitted = [f for f in schema.fields if not f.is_filler]
        arrow_fields = [(f.name, self._map_arrow_type(f)) for f in emitted]
        arrow_schema = pa.schema(arrow_fields)
        columns: dict[str, list] = {f.name: [] for f in emitted}
        for row in rows:
            for f in emitted:
                columns[f.name].append(self._coerce_cell(f, row.get(f.name)))
        return pa.Table.from_pydict(columns, schema=arrow_schema)

    def write(
        self,
        schema: FileSchemaDefinition,
        rows: list[dict],
        output_path: Path,
    ) -> Path:
        self._ensure_writable(schema, rows, output_path)

        import pyarrow.parquet as pq

        table = self._build_arrow_table(schema, rows)
        with write_atomic(output_path, mode="wb") as handle:
            if schema.file_format == FileFormat.PARQUET.value:
                pq.write_table(table, handle, compression=self._compression)
            elif schema.file_format == FileFormat.ORC.value:
                from pyarrow import orc  # local lazy import

                orc.write_table(
                    table,
                    handle,
                    compression=(self._compression or "uncompressed").upper(),
                )
            else:  # pragma: no cover - validate_schema rejected this above
                raise ValueError(
                    f"ColumnarWriter cannot write file_format={schema.file_format!r}"
                )

        return output_path
