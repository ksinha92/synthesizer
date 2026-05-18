"""Fixed-width writer — position-correct ASCII records.

Padding rules:
  - alphanumeric: right-pad with `pad_char` (default space)
  - numeric: left-pad with `num_pad_char` (default zero)
  - decimal: literal '.' unless schema.metadata["implied_decimal"] is true,
    in which case the point is dropped and the digits are zero-padded to `length`

Filler fields emit `pad_char` × byte_length. REDEFINES fields are not
serialized separately — they share storage with their target.
"""

from __future__ import annotations

import structlog
from pathlib import Path

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.base_writer import BaseFileWriter, write_atomic

logger = structlog.get_logger()


class FixedWidthWriter(BaseFileWriter):
    """Write rows as fixed-width ASCII records."""

    def __init__(
        self,
        pad_char: str = " ",
        num_pad_char: str = "0",
        record_terminator: bytes = b"\n",
        encoding: str = "ascii",
        leading_sign: bool = True,
    ) -> None:
        self._pad_char = pad_char
        self._num_pad_char = num_pad_char
        self._record_terminator = record_terminator
        self._encoding = encoding
        self._leading_sign = leading_sign

    @classmethod
    def supported_formats(cls) -> set[FileFormat]:
        return {FileFormat.FIXED_WIDTH}

    def get_extension(self) -> str:
        return "txt"

    def validate_schema(self, schema: FileSchemaDefinition) -> list[str]:
        """Domain validation plus ASCII-fixed-width specific guards.

        Signed numeric/decimal fields use COBOL overpunch encoding (the sign
        nibble is fused onto the last digit, so `byte_length == digits`).
        That requires the same EBCDIC/overpunch machinery as VSAM and is the
        responsibility of VSAMWriter in Plan 44-02. Reject here with a clear
        message rather than emit subtly-wrong bytes.

        Binary and packed_decimal fields are also COMP / COMP-3 territory
        — same deferral.
        """
        errors = list(super().validate_schema(schema))
        for f in schema.fields:
            if f.is_filler:
                continue
            if f.signed and f.data_type in ("numeric", "decimal"):
                errors.append(
                    f"Field {f.name!r} is signed; signed display numerics use COBOL "
                    f"overpunch encoding and are emitted by VSAMWriter (Plan 44-02), "
                    f"not FixedWidthWriter"
                )
            if f.data_type in ("binary", "packed_decimal"):
                errors.append(
                    f"Field {f.name!r} has data_type={f.data_type!r}; COMP / COMP-3 "
                    f"fields are emitted by VSAMWriter (Plan 44-02), not FixedWidthWriter"
                )
        return errors

    # ── Field rendering ────────────────────────────────────────────────

    def _render_field(
        self,
        field: FileFieldDefinition,
        value,
        implied_decimal: bool,
    ) -> bytes:
        pad_byte = self._pad_char.encode(self._encoding)
        if field.is_filler:
            return pad_byte * field.byte_length

        if value is None:
            # Treat None as pad-filled regardless of nullable flag.
            return pad_byte * field.byte_length

        data_type = field.data_type
        if data_type == "alphanumeric":
            text = str(value)
            encoded = text.encode(self._encoding)
            if len(encoded) > field.byte_length:
                logger.warning(
                    "fixed_width_truncation",
                    field=field.name,
                    length=field.byte_length,
                    actual=len(encoded),
                )
                encoded = encoded[: field.byte_length]
            return encoded.ljust(field.byte_length, pad_byte)

        if data_type == "numeric":
            ival = int(value)
            if field.signed and self._leading_sign:
                sign = b"-" if ival < 0 else (b"+" if ival > 0 else b" ")
                digits = str(abs(ival)).encode(self._encoding)
                width = field.byte_length - 1
                if len(digits) > width:
                    raise ValueError(
                        f"Field {field.name!r} numeric value {ival} exceeds length {field.length}"
                    )
                rendered = sign + digits.rjust(width, self._num_pad_char.encode(self._encoding))
            else:
                digits = str(ival).encode(self._encoding)
                if len(digits) > field.byte_length:
                    raise ValueError(
                        f"Field {field.name!r} numeric value {ival} exceeds length {field.length}"
                    )
                rendered = digits.rjust(field.byte_length, self._num_pad_char.encode(self._encoding))
            return rendered

        if data_type == "decimal":
            fval = float(value)
            decimals = max(field.decimal_places, 0)
            if implied_decimal:
                # No literal '.'; pack as zero-padded digits scaled by 10**decimals.
                scaled = int(round(fval * (10 ** decimals)))
                if field.signed and self._leading_sign:
                    sign = b"-" if scaled < 0 else (b"+" if scaled > 0 else b" ")
                    digits = str(abs(scaled)).encode(self._encoding)
                    width = field.byte_length - 1
                    rendered = sign + digits.rjust(width, self._num_pad_char.encode(self._encoding))
                else:
                    digits = str(abs(scaled)).encode(self._encoding) if scaled >= 0 else None
                    if digits is None:
                        raise ValueError(
                            f"Field {field.name!r} unsigned implied decimal cannot store negative {fval}"
                        )
                    rendered = digits.rjust(field.byte_length, self._num_pad_char.encode(self._encoding))
            else:
                formatted = f"{fval:.{decimals}f}"
                encoded = formatted.encode(self._encoding)
                if len(encoded) > field.byte_length:
                    raise ValueError(
                        f"Field {field.name!r} decimal value {fval} exceeds length {field.length}"
                    )
                rendered = encoded.rjust(field.byte_length, self._num_pad_char.encode(self._encoding))
            return rendered

        # Guard rail (not a stub). FixedWidthWriter is an ASCII flat-file
        # emitter and intentionally rejects COBOL/EBCDIC-only types
        # (packed_decimal, binary, COMP / COMP-3) — those belong on
        # VSAMWriter. Supported: alphanumeric, numeric, decimal.
        raise NotImplementedError(
            f"FixedWidthWriter cannot render data_type {data_type!r} (field {field.name!r}); "
            f"supported: alphanumeric, numeric, decimal. "
            f"For packed_decimal / binary, use VSAMWriter."
        )

    # ── Write ───────────────────────────────────────────────────────────

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

        implied_decimal = bool((schema.metadata or {}).get("implied_decimal", False))

        # Skip REDEFINES fields — their target's bytes fill that range.
        emitted = [f for f in schema.fields if f.redefines is None]
        # Sort by start_position for deterministic write order (and easier debugging).
        emitted.sort(key=lambda f: f.start_position)

        pad_byte = self._pad_char.encode(self._encoding)

        with write_atomic(output_path, mode="wb") as handle:
            for row in rows:
                record = bytearray(pad_byte * record_length)
                for field in emitted:
                    rendered = self._render_field(field, row.get(field.name), implied_decimal)
                    if len(rendered) != field.byte_length:
                        raise ValueError(
                            f"Field {field.name!r} rendered {len(rendered)} bytes, "
                            f"expected {field.byte_length}"
                        )
                    record[
                        field.start_position : field.start_position + field.byte_length
                    ] = rendered
                if len(record) != record_length:
                    raise ValueError(
                        f"Record length {len(record)} != schema record_length {record_length}"
                    )
                handle.write(bytes(record))
                handle.write(self._record_terminator)

        return output_path
