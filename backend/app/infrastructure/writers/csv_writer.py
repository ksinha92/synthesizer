"""CSV writer — RFC 4180 minimal-quoting, configurable delimiter / encoding / BOM."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from app.domain.synthetic.file_schema import FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.base_writer import BaseFileWriter, write_atomic


class CSVWriter(BaseFileWriter):
    """Write rows as CSV.

    Filler fields are skipped (no header column, no data column).
    None / missing values serialize as the empty string.
    Floats are formatted using each field's `decimal_places`.
    """

    def __init__(
        self,
        delimiter: str = ",",
        quotechar: str = '"',
        line_terminator: str = "\r\n",
        encoding: str = "utf-8",
        include_header: bool = True,
        write_bom: bool = False,
    ) -> None:
        self._delimiter = delimiter
        self._quotechar = quotechar
        self._line_terminator = line_terminator
        self._encoding = encoding
        self._include_header = include_header
        self._write_bom = write_bom

    @classmethod
    def supported_formats(cls) -> set[FileFormat]:
        return {FileFormat.CSV}

    def get_extension(self) -> str:
        return "csv"

    def write(
        self,
        schema: FileSchemaDefinition,
        rows: list[dict],
        output_path: Path,
    ) -> Path:
        self._ensure_writable(schema, rows, output_path)

        emitted_fields = [f for f in schema.fields if not f.is_filler]
        emitted_names = [f.name for f in emitted_fields]
        decimal_places_by_name = {
            f.name: f.decimal_places for f in emitted_fields if f.decimal_places > 0
        }

        with write_atomic(output_path, mode="wb") as binary_handle:
            if self._write_bom and self._encoding.lower().replace("-", "") == "utf8":
                binary_handle.write(b"\xef\xbb\xbf")

            # newline="" prevents csv from translating line terminators itself;
            # we control terminators via lineterminator below.
            text_handle = io.TextIOWrapper(
                binary_handle, encoding=self._encoding, newline=""
            )
            try:
                writer = csv.writer(
                    text_handle,
                    delimiter=self._delimiter,
                    quotechar=self._quotechar,
                    quoting=csv.QUOTE_MINIMAL,
                    lineterminator=self._line_terminator,
                )

                if self._include_header:
                    writer.writerow(emitted_names)

                for row in rows:
                    out_row = []
                    for name in emitted_names:
                        value = row.get(name)
                        if value is None:
                            out_row.append("")
                        elif isinstance(value, float) and name in decimal_places_by_name:
                            out_row.append(
                                f"{value:.{decimal_places_by_name[name]}f}"
                            )
                        else:
                            out_row.append(str(value))
                    writer.writerow(out_row)

                text_handle.flush()
            finally:
                # Detach so the binary handle is closed exactly once by write_atomic.
                text_handle.detach()

        return output_path
