"""VSAM writer — EBCDIC + COMP / COMP-3 + RDW for variable records.

Handles both `VSAM_FIXED` and `VSAM_VARIABLE`. Files contain no record
terminators; in variable mode each record is preceded by a 4-byte big-endian
RDW (record-descriptor word) whose length includes the RDW itself.
"""

from __future__ import annotations

import structlog
from pathlib import Path

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers import cobol_encoding as cobol
from app.infrastructure.writers import ebcdic_codec as ebcdic
from app.infrastructure.writers.base_writer import BaseFileWriter, write_atomic

logger = structlog.get_logger()


_ALLOWED_ENCODINGS = {"ebcdic_cp037", "ebcdic_cp1140"}
_ALLOWED_FORMATS = {
    FileFormat.VSAM_FIXED.value,
    FileFormat.VSAM_VARIABLE.value,
}


class VSAMWriter(BaseFileWriter):
    """Emit VSAM records in EBCDIC with COMP / COMP-3 / overpunch support."""

    @classmethod
    def supported_formats(cls) -> set[FileFormat]:
        return {FileFormat.VSAM_FIXED, FileFormat.VSAM_VARIABLE}

    def get_extension(self) -> str:
        return "vsam"

    def validate_schema(self, schema: FileSchemaDefinition) -> list[str]:
        errors = list(super().validate_schema(schema))
        if schema.file_format not in _ALLOWED_FORMATS:
            errors.append(
                f"VSAMWriter rejects file_format={schema.file_format!r}; "
                f"expected one of {sorted(_ALLOWED_FORMATS)}"
            )
        if schema.encoding not in _ALLOWED_ENCODINGS:
            errors.append(
                f"VSAMWriter rejects encoding={schema.encoding!r}; "
                f"expected one of {sorted(_ALLOWED_ENCODINGS)}"
            )
        for f in schema.fields:
            if f.is_filler:
                continue
            if f.data_type == "alphanumeric" and f.signed:
                errors.append(
                    f"Field {f.name!r}: alphanumeric fields cannot be signed"
                )
        return errors

    # ── Field rendering ────────────────────────────────────────────────

    def _render_field(
        self,
        field: FileFieldDefinition,
        value,
        encoding: str,
        implied_decimal: bool,
    ) -> bytes:
        if field.is_filler:
            return ebcdic.space(encoding) * field.byte_length
        if value is None:
            return ebcdic.space(encoding) * field.byte_length

        comp = field.comp_type
        data_type = field.data_type

        # COMP / COMP-3 dispatch — applies to numeric, decimal, binary, packed_decimal.
        if comp == "comp_3" or data_type == "packed_decimal":
            scaled = self._scale_to_int(value, field.decimal_places)
            out = cobol.encode_comp3(scaled, field.length, field.signed)
            self._assert_length(field, out)
            return out

        if comp == "comp" or data_type == "binary":
            scaled = self._scale_to_int(value, field.decimal_places)
            out = cobol.encode_comp(scaled, field.length, field.signed)
            self._assert_length(field, out)
            return out

        # Display formats (no COMP) ─────────────────────────────────────
        if data_type == "alphanumeric":
            text = str(value)
            encoded = ebcdic.encode(text, encoding)
            if len(encoded) > field.byte_length:
                logger.warning(
                    "vsam_truncation",
                    field=field.name,
                    length=field.byte_length,
                    actual=len(encoded),
                )
                encoded = encoded[: field.byte_length]
            return encoded.ljust(field.byte_length, ebcdic.space(encoding))

        if data_type in ("numeric", "decimal"):
            if data_type == "decimal" and not implied_decimal:
                # Rare for VSAM, but honor explicit decimal points if asked.
                decimals = max(field.decimal_places, 0)
                formatted = f"{abs(float(value)):.{decimals}f}"
                if len(formatted) > field.byte_length:
                    raise OverflowError(
                        f"Field {field.name!r} decimal value {value} exceeds length {field.length}"
                    )
                encoded = ebcdic.encode(formatted, encoding)
                return encoded.rjust(field.byte_length, ebcdic.zero(encoding))

            scaled = self._scale_to_int(value, field.decimal_places)
            if field.signed:
                out = cobol.encode_display_signed(scaled, field.length, encoding)
                self._assert_length(field, out)
                return out

            digits = str(abs(scaled))
            if len(digits) > field.length:
                raise OverflowError(
                    f"Field {field.name!r} value {value} has {len(digits)} digits, declared {field.length}"
                )
            encoded = ebcdic.encode(digits, encoding)
            return encoded.rjust(field.byte_length, ebcdic.zero(encoding))

        # Guard rail (not a stub). VSAMWriter renders the full COBOL/EBCDIC
        # data_type matrix used by Ameritas mainframe extracts:
        #   alphanumeric, numeric (display | comp | comp_3),
        #   decimal, packed_decimal, binary.
        # Reaching this branch means the schema declares a data_type outside
        # that set — fail fast rather than silently emit garbage bytes. The
        # caller will see a 422 from /file-sets/generate.
        raise NotImplementedError(
            f"VSAMWriter cannot render data_type {data_type!r} (field {field.name!r}); "
            f"supported: alphanumeric, numeric, decimal, packed_decimal, binary"
        )

    @staticmethod
    def _scale_to_int(value, decimal_places: int) -> int:
        if decimal_places > 0:
            return int(round(float(value) * (10 ** decimal_places)))
        return int(value)

    @staticmethod
    def _assert_length(field: FileFieldDefinition, rendered: bytes) -> None:
        if len(rendered) != field.byte_length:
            raise ValueError(
                f"Field {field.name!r} rendered {len(rendered)} bytes, "
                f"expected byte_length={field.byte_length}"
            )

    # ── Write ──────────────────────────────────────────────────────────

    def write(
        self,
        schema: FileSchemaDefinition,
        rows: list[dict],
        output_path: Path,
    ) -> Path:
        self._ensure_writable(schema, rows, output_path)

        record_length = schema.compute_record_length()
        if record_length <= 0:
            raise ValueError(
                f"Schema {schema.name!r} has non-positive record_length {record_length}"
            )

        encoding = schema.encoding
        implied_decimal = bool((schema.metadata or {}).get("implied_decimal", True))
        is_variable = schema.file_format == FileFormat.VSAM_VARIABLE.value

        emitted = [f for f in schema.fields if f.redefines is None]
        emitted.sort(key=lambda f: f.start_position)

        ebcdic_space = ebcdic.space(encoding)

        with write_atomic(output_path, mode="wb") as handle:
            for row in rows:
                record = bytearray(ebcdic_space * record_length)
                for field in emitted:
                    rendered = self._render_field(
                        field, row.get(field.name), encoding, implied_decimal
                    )
                    record[
                        field.start_position : field.start_position + field.byte_length
                    ] = rendered
                if len(record) != record_length:  # pragma: no cover
                    raise ValueError(
                        f"Record length {len(record)} != schema record_length {record_length}"
                    )
                if is_variable:
                    rdw_len = (record_length + 4).to_bytes(2, "big")
                    handle.write(rdw_len + b"\x00\x00")
                handle.write(bytes(record))

        return output_path
