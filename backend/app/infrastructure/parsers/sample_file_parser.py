"""Sample file parsers — reverse Phase 44 writers into pandas DataFrames.

One parser per FileFormat. The dispatcher `parse(path, schema)` picks the
right one and returns a DataFrame whose columns equal the schema's non-filler
field names.

VSAM parsing reverses the COMP-3 nibble packing, EBCDIC overpunch, and
RDW framing established in Plan 44-02 — round-trip-safe with VSAMWriter.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.domain.synthetic.file_schema import FileFieldDefinition, FileSchemaDefinition
from app.infrastructure.writers import ebcdic_codec


# ── Reverse overpunch maps (last-digit byte → digit + sign) ─────────────────
_POS_OVERPUNCH_REV = {
    "{": ("0", +1),
    "A": ("1", +1), "B": ("2", +1), "C": ("3", +1), "D": ("4", +1), "E": ("5", +1),
    "F": ("6", +1), "G": ("7", +1), "H": ("8", +1), "I": ("9", +1),
}
_NEG_OVERPUNCH_REV = {
    "}": ("0", -1),
    "J": ("1", -1), "K": ("2", -1), "L": ("3", -1), "M": ("4", -1), "N": ("5", -1),
    "O": ("6", -1), "P": ("7", -1), "Q": ("8", -1), "R": ("9", -1),
}


# ── CSV ─────────────────────────────────────────────────────────────────────
def parse_csv(path: Path, schema: FileSchemaDefinition, **csv_opts) -> pd.DataFrame:
    """Read a CSV produced by CSVWriter into a DataFrame."""
    df = pd.read_csv(path, **csv_opts)
    expected = [f.name for f in schema.fields if not f.is_filler]
    extra = set(df.columns) - set(expected)
    missing = set(expected) - set(df.columns)
    if extra or missing:
        raise ValueError(
            f"CSV columns {list(df.columns)} do not match schema fields {expected}; "
            f"extra={sorted(extra)}, missing={sorted(missing)}"
        )
    return df


# ── Fixed-width ─────────────────────────────────────────────────────────────
def parse_fixed_width(path: Path, schema: FileSchemaDefinition) -> pd.DataFrame:
    """Read a fixed-width file produced by FixedWidthWriter into a DataFrame."""
    emitted = [f for f in schema.fields if not f.is_filler and f.redefines is None]
    emitted.sort(key=lambda f: f.start_position)

    colspecs = [(f.start_position, f.start_position + f.byte_length) for f in emitted]
    names = [f.name for f in emitted]
    df = pd.read_fwf(path, colspecs=colspecs, names=names, dtype=str)

    implied_decimal = bool((schema.metadata or {}).get("implied_decimal", False))

    for f in emitted:
        col = df[f.name]
        if f.data_type == "numeric":
            df[f.name] = col.astype(str).str.strip().astype(int)
        elif f.data_type == "decimal":
            if implied_decimal:
                scaled = col.astype(str).str.strip().astype(int)
                df[f.name] = scaled / (10 ** f.decimal_places)
            else:
                df[f.name] = col.astype(str).str.strip().astype(float)
        else:
            df[f.name] = col.astype(str).str.rstrip()

    return df


# ── VSAM ────────────────────────────────────────────────────────────────────
def _decode_comp3(data: bytes, digits: int, signed: bool) -> int:
    """Reverse encode_comp3: unpack nibbles, apply sign nibble."""
    nibbles = []
    for byte in data:
        nibbles.append((byte >> 4) & 0xF)
        nibbles.append(byte & 0xF)

    expected_nibbles = digits + 1
    # Strip the leading pad nibble if the digit count is odd.
    if len(nibbles) > expected_nibbles:
        nibbles = nibbles[len(nibbles) - expected_nibbles :]

    digit_nibbles = nibbles[:-1]
    sign_nibble = nibbles[-1]
    digit_str = "".join(str(n) for n in digit_nibbles)
    value = int(digit_str) if digit_str else 0
    if signed and sign_nibble == 0xD:
        value = -value
    return value


def _decode_display_signed(data: bytes, encoding: str) -> int:
    """Reverse encode_display_signed: head digits + overpunched last byte."""
    head = data[:-1]
    tail = data[-1:]
    head_text = head.decode(ebcdic_codec.to_python_codec(encoding))
    tail_char = tail.decode(ebcdic_codec.to_python_codec(encoding))

    if tail_char in _POS_OVERPUNCH_REV:
        digit, sign = _POS_OVERPUNCH_REV[tail_char]
    elif tail_char in _NEG_OVERPUNCH_REV:
        digit, sign = _NEG_OVERPUNCH_REV[tail_char]
    else:
        # No overpunch — treat as plain digit (unsigned positive)
        digit, sign = tail_char, +1

    digit_str = (head_text + digit).strip()
    if not digit_str.lstrip("0"):
        return 0
    return sign * int(digit_str)


def _decode_field(data: bytes, field: FileFieldDefinition, encoding: str):
    """Decode a single field's bytes into a Python value.

    Supported ``data_type`` × ``comp_type`` combinations:

    ====================  ==============  ===============================
    data_type             comp_type       Decoding
    ====================  ==============  ===============================
    ``packed_decimal``    any             COMP-3 nibble unpack
    ``numeric``           ``comp_3``      COMP-3 nibble unpack
    ``binary``            any             Big-endian signed/unsigned int
    ``numeric``           ``comp``        Big-endian signed/unsigned int
    ``alphanumeric``      any             EBCDIC text + rstrip
    ``numeric``           ``display``     EBCDIC digits + overpunch sign
    ``decimal``           ``display``     EBCDIC digits + decimal scaling
    ====================  ==============  ===============================

    Anything outside this matrix raises :class:`NotImplementedError` so a
    malformed schema (or a future ``data_type`` we don't yet round-trip)
    fails loud instead of silently returning garbage. This is a guard
    rail, not a stub — VSAMWriter rejects the same combinations at write
    time, so a file we wrote can always be parsed.
    """
    if field.is_filler:
        return None

    if field.comp_type == "comp_3" or field.data_type == "packed_decimal":
        scaled = _decode_comp3(data, field.length, field.signed)
        if field.decimal_places > 0:
            return scaled / (10 ** field.decimal_places)
        return scaled

    if field.comp_type == "comp" or field.data_type == "binary":
        return int.from_bytes(data, "big", signed=field.signed)

    if field.data_type == "alphanumeric":
        return data.decode(ebcdic_codec.to_python_codec(encoding)).rstrip()

    if field.data_type in ("numeric", "decimal"):
        if field.signed:
            scaled = _decode_display_signed(data, encoding)
        else:
            text = data.decode(ebcdic_codec.to_python_codec(encoding))
            stripped = text.strip()
            scaled = int(stripped) if stripped else 0
        if field.data_type == "decimal" and field.decimal_places > 0:
            return scaled / (10 ** field.decimal_places)
        return scaled

    raise NotImplementedError(
        f"parse_vsam cannot decode data_type {field.data_type!r} for field {field.name!r}"
    )


def parse_vsam(path: Path, schema: FileSchemaDefinition) -> pd.DataFrame:
    """Read a VSAM file produced by VSAMWriter into a DataFrame."""
    record_length = schema.compute_record_length()
    is_variable = schema.file_format == "vsam_variable"
    encoding = schema.encoding

    emitted = [f for f in schema.fields if not f.is_filler and f.redefines is None]
    emitted.sort(key=lambda f: f.start_position)

    data = Path(path).read_bytes()
    rows = []
    offset = 0
    record_size = record_length + (4 if is_variable else 0)
    while offset + record_size <= len(data):
        if is_variable:
            rdw = data[offset : offset + 4]
            declared = int.from_bytes(rdw[0:2], "big")
            if declared != record_length + 4:
                raise ValueError(
                    f"Bad RDW at offset {offset}: declared={declared}, expected={record_length + 4}"
                )
            offset += 4
        record = data[offset : offset + record_length]
        offset += record_length

        row = {}
        for f in emitted:
            chunk = record[f.start_position : f.start_position + f.byte_length]
            row[f.name] = _decode_field(chunk, f, encoding)
        rows.append(row)

    return pd.DataFrame(rows, columns=[f.name for f in emitted])


# ── Parquet / ORC ───────────────────────────────────────────────────────────
def parse_columnar(path: Path, schema: FileSchemaDefinition) -> pd.DataFrame:
    """Read a Parquet or ORC file produced by ColumnarWriter into a DataFrame."""
    if schema.file_format == "parquet":
        import pyarrow.parquet as pq

        table = pq.read_table(path)
    elif schema.file_format == "orc":
        from pyarrow import orc

        table = orc.read_table(path)
    else:
        raise ValueError(f"parse_columnar got unexpected format {schema.file_format!r}")

    df = table.to_pandas()
    # Convert Decimal columns to float for downstream convenience.
    for f in schema.fields:
        if f.is_filler:
            continue
        if f.data_type in ("decimal", "packed_decimal") and f.name in df.columns:
            df[f.name] = df[f.name].apply(
                lambda v: float(v) if v is not None else None
            )
    return df


# ── Dispatcher ─────────────────────────────────────────────────────────────
def parse(path: Path, schema: FileSchemaDefinition) -> pd.DataFrame:
    """Top-level dispatch by `schema.file_format`."""
    fmt = schema.file_format
    if fmt == "csv":
        return parse_csv(path, schema)
    if fmt == "fixed_width":
        return parse_fixed_width(path, schema)
    if fmt in ("vsam_fixed", "vsam_variable"):
        return parse_vsam(path, schema)
    if fmt in ("parquet", "orc"):
        return parse_columnar(path, schema)
    raise ValueError(f"No parser for file_format={fmt!r}")
