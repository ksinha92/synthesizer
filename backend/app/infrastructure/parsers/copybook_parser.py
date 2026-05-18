"""COBOL copybook parser. Converts PIC clauses into FileSchemaDefinition instances."""

from __future__ import annotations

import math
import re
from enum import Enum
from pathlib import Path

import structlog

from app.domain.synthetic.file_schema import (
    FileFieldDefinition,
    FileSchemaDefinition,
    LayoutVariant,
)
from app.domain.synthetic.value_objects import CompType, EncodingType, FileFormat

logger = structlog.get_logger()

# Maximum input limits
MAX_COPYBOOK_BYTES = 1_048_576  # 1 MB
MAX_COPYBOOK_LINES = 10_000


class SplitStrategy(str, Enum):
    """How to handle copybooks with multiple record layouts."""

    SINGLE = "single"                 # Existing behavior: one flat field list
    SPLIT_01_LEVEL = "split_01"       # One LayoutVariant per 01-level entry
    SPLIT_REDEFINE = "split_redefine" # One LayoutVariant per REDEFINES branch


class CopybookParser:
    """Parse COBOL copybook text into FileSchemaDefinition."""

    def parse(
        self,
        copybook_text: str,
        name: str = "copybook",
        default_format: FileFormat = FileFormat.VSAM_FIXED,
        default_encoding: EncodingType = EncodingType.EBCDIC_CP037,
        split_strategy: SplitStrategy = SplitStrategy.SINGLE,
    ) -> FileSchemaDefinition:
        """Parse a COBOL copybook string into a FileSchemaDefinition.

        Args:
            copybook_text: Raw COBOL copybook text.
            name: Name for the resulting schema.
            default_format: Default file format (VSAM_FIXED).
            default_encoding: Default encoding (EBCDIC_CP037).
            split_strategy: How to handle multi-record layouts. ``SINGLE``
                keeps the flat list (legacy behavior). ``SPLIT_01_LEVEL``
                emits one LayoutVariant per 01-level entry (File-AID style
                multi-record book). ``SPLIT_REDEFINE`` emits one variant
                per REDEFINES branch. When the strategy can't find
                anything to split, behavior degrades to ``SINGLE``.

        Returns:
            FileSchemaDefinition with parsed fields, possibly with
            ``layout_variants`` populated.

        Raises:
            ValueError: If input exceeds size limits or contains
                unparseable content.
        """
        # Input size guard
        if len(copybook_text.encode("utf-8", errors="replace")) > MAX_COPYBOOK_BYTES:
            raise ValueError("Copybook exceeds size limit (max 1MB)")

        lines = copybook_text.splitlines()
        if len(lines) > MAX_COPYBOOK_LINES:
            raise ValueError(f"Copybook exceeds size limit (max {MAX_COPYBOOK_LINES} lines)")

        warnings: list[str] = []
        entries = self._preprocess_and_extract(lines, warnings)

        if split_strategy == SplitStrategy.SPLIT_01_LEVEL:
            base_fields, variants = self._build_split_01(entries, warnings)
        elif split_strategy == SplitStrategy.SPLIT_REDEFINE:
            base_fields, variants = self._build_split_redefine(entries, warnings)
        else:
            base_fields = self._build_fields(entries, warnings)
            variants = []

        record_length = sum(f.byte_length for f in base_fields if f.redefines is None)

        schema = FileSchemaDefinition(
            name=name,
            fields=base_fields,
            file_format=default_format.value,
            encoding=default_encoding.value,
            record_length=record_length,
            layout_variants=variants,
            # COBOL decimals are always implied (no literal '.' in storage).
            # FixedWidthWriter and VSAMWriter honor this flag from schema.metadata.
            metadata={
                "source_copybook": name,
                "warnings": warnings,
                "implied_decimal": True,
                "split_strategy": split_strategy.value,
            },
        )

        return schema

    # ── Split strategies ────────────────────────────────────────────

    def _build_split_01(
        self, entries: list[dict], warnings: list[str]
    ) -> tuple[list[FileFieldDefinition], list[LayoutVariant]]:
        """Partition entries by 01-level boundary; first partition is base."""
        partitions: list[tuple[str, list[dict]]] = []
        current_name = "Record"
        current: list[dict] = []
        for e in entries:
            if e["level"] == 1 and current:
                partitions.append((current_name, current))
                current_name = e["name"]
                current = []
            elif e["level"] == 1:
                current_name = e["name"]
            current.append(e)
        if current:
            partitions.append((current_name, current))

        if len(partitions) <= 1:
            # Nothing to split — fall back to single-layout behavior.
            return self._build_fields(entries, warnings), []

        base_name, base_entries = partitions[0]
        base_fields = self._build_fields(base_entries, warnings)
        variants: list[LayoutVariant] = []
        for vname, ventries in partitions[1:]:
            variant_fields = self._build_fields(list(ventries), warnings)
            variants.append(
                LayoutVariant(
                    name=vname or f"Layout_{len(variants) + 1}",
                    fields=variant_fields,
                    conditions=[],  # The wizard will let the user set these.
                )
            )
        return base_fields, variants

    def _build_split_redefine(
        self, entries: list[dict], warnings: list[str]
    ) -> tuple[list[FileFieldDefinition], list[LayoutVariant]]:
        """Pull each REDEFINES branch into its own LayoutVariant.

        The non-REDEFINES entries form the base. Each REDEFINES group
        (one or more entries sharing the same ``redefines`` target)
        becomes a separate variant overlaying that target.
        """
        base_entries = [e for e in entries if not e.get("redefines")]
        redef_groups: dict[str, list[dict]] = {}
        for e in entries:
            if e.get("redefines"):
                redef_groups.setdefault(e["redefines"], []).append(e)

        if not redef_groups:
            return self._build_fields(entries, warnings), []

        base_fields = self._build_fields(base_entries, warnings)
        variants: list[LayoutVariant] = []
        for target, group in redef_groups.items():
            # Build a variant whose fields are the base UP TO the redefined
            # target, plus the redefines branch in place of it. We do this
            # by feeding the parser the base entries with the redefines
            # branch substituted at the target's position.
            substituted = self._substitute_redefines(base_entries, target, group)
            variant_fields = self._build_fields(substituted, warnings)
            variants.append(
                LayoutVariant(
                    name=f"{target}_Redef_{len(variants) + 1}",
                    fields=variant_fields,
                    conditions=[],
                )
            )
        return base_fields, variants

    @staticmethod
    def _substitute_redefines(
        base_entries: list[dict], target_name: str, redef_group: list[dict]
    ) -> list[dict]:
        """Return a copy of base_entries with the target entry replaced by the redef group."""
        out: list[dict] = []
        replaced = False
        for e in base_entries:
            if not replaced and e["name"].upper() == target_name.upper():
                # Drop ``redefines`` on each substituted entry so its
                # offset computes from the natural sequence rather than
                # overlaying. The variant occupies the same byte range
                # as the original target.
                for r in redef_group:
                    out.append({**r, "redefines": None})
                replaced = True
            else:
                out.append(e)
        if not replaced:
            out.extend(redef_group)
        return out

    def parse_file(
        self,
        file_path: Path,
        **kwargs,
    ) -> FileSchemaDefinition:
        """Parse a copybook file from disk."""
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if "name" not in kwargs:
            kwargs["name"] = file_path.stem
        return self.parse(text, **kwargs)

    # ── Internal Methods ────────────────────────────────────────────

    def _preprocess_and_extract(
        self, lines: list[str], warnings: list[str]
    ) -> list[dict]:
        """Pre-process copybook lines and extract entries."""
        cleaned: list[tuple[int, str]] = []  # (original_line_number, text)

        for i, raw_line in enumerate(lines, start=1):
            # Strip sequence numbers (cols 1-6) if line is long enough
            if len(raw_line) >= 7:
                indicator = raw_line[6]
                text = raw_line[7:]

                # Comment line
                if indicator == "*" or indicator == "/":
                    continue

                # Continuation line — append to previous
                if indicator == "-" and cleaned:
                    prev_lineno, prev_text = cleaned[-1]
                    cleaned[-1] = (prev_lineno, prev_text.rstrip() + " " + text.strip())
                    continue

                text = text.strip()
            else:
                # Short line — treat as free-form
                text = raw_line.strip()

            if not text or text.startswith("*"):
                continue

            # Remove inline comments (after period or standalone)
            text = re.sub(r"\.\s*$", ".", text)  # Keep period at end

            cleaned.append((i, text))

        # Join continuation and split into entries by level number
        entries: list[dict] = []
        current_text = ""
        current_line = 0

        for lineno, text in cleaned:
            # Check if this starts a new entry (level number at start)
            level_match = re.match(r"^(\d{1,2})\s+", text)
            if level_match:
                if current_text:
                    entry = self._parse_entry(current_text, current_line, warnings)
                    if entry:
                        entries.append(entry)
                current_text = text
                current_line = lineno
            else:
                current_text += " " + text

        # Last entry
        if current_text:
            entry = self._parse_entry(current_text, current_line, warnings)
            if entry:
                entries.append(entry)

        return entries

    def _parse_entry(
        self, text: str, line_number: int, warnings: list[str]
    ) -> dict | None:
        """Parse a single copybook entry into a structured dict."""
        # Remove trailing period
        text = text.rstrip(". ")

        # Extract level number
        level_match = re.match(r"^(\d{1,2})\s+(.*)", text)
        if not level_match:
            return None

        level = int(level_match.group(1))
        remainder = level_match.group(2).strip()

        # Skip level 88 (condition names)
        if level == 88:
            warnings.append(f"Line {line_number}: Skipped level 88 condition name")
            return None

        # Extract field name
        name_match = re.match(r"^(\S+)\s*(.*)", remainder)
        if not name_match:
            return None

        field_name = name_match.group(1).upper()
        rest = name_match.group(2).strip()

        entry: dict = {
            "level": level,
            "name": field_name,
            "pic": None,
            "comp_type": CompType.NONE,
            "redefines": None,
            "occurs": 1,
            "line_number": line_number,
            "is_group": True,  # Assume group until PIC found
        }

        # Parse clauses from remainder
        rest_upper = rest.upper()

        # REDEFINES
        redef_match = re.search(r"REDEFINES\s+(\S+)", rest_upper)
        if redef_match:
            entry["redefines"] = redef_match.group(1)

        # OCCURS
        occurs_match = re.search(r"OCCURS\s+(\d+)", rest_upper)
        if occurs_match:
            entry["occurs"] = int(occurs_match.group(1))

        # PIC / PICTURE clause
        pic_match = re.search(r"(?:PIC|PICTURE)\s+IS\s+(\S+)|(?:PIC|PICTURE)\s+(\S+)", rest_upper)
        if pic_match:
            entry["pic"] = pic_match.group(1) or pic_match.group(2)
            entry["is_group"] = False

        # COMP type (must check after PIC extraction)
        if re.search(r"COMP-3|COMPUTATIONAL-3|PACKED-DECIMAL", rest_upper):
            entry["comp_type"] = CompType.COMP_3
        elif re.search(r"COMP\b|COMPUTATIONAL\b|BINARY\b", rest_upper):
            entry["comp_type"] = CompType.COMP

        return entry

    def _build_fields(
        self, entries: list[dict], warnings: list[str]
    ) -> list[FileFieldDefinition]:
        """Convert parsed entries into FileFieldDefinition list with computed positions."""
        fields: list[FileFieldDefinition] = []
        byte_offset = 0
        filler_counter = 0
        redefines_positions: dict[str, int] = {}  # field_name -> start_position
        occurs_depth = 0  # Track nesting for nested OCCURS rejection

        for entry in entries:
            # Skip group-level entries (no PIC clause)
            if entry["is_group"]:
                if entry["occurs"] > 1:
                    occurs_depth += 1
                warnings.append(
                    f"Line {entry['line_number']}: Skipped group-level entry '{entry['name']}'"
                )
                continue

            # Check for nested OCCURS
            if entry["occurs"] > 1 and occurs_depth > 0:
                raise ValueError(
                    f"Nested OCCURS not supported at line {entry['line_number']}: "
                    f"field '{entry['name']}' has OCCURS inside an already-expanding group"
                )

            # Parse PIC clause
            pic = entry["pic"]
            if not pic:
                warnings.append(
                    f"Line {entry['line_number']}: Skipped entry '{entry['name']}' (no PIC clause)"
                )
                continue

            try:
                data_type, length, decimal_places, signed = self._parse_pic(pic)
            except ValueError as e:
                raise ValueError(
                    f"Invalid PIC clause '{pic}' at line {entry['line_number']}: {e}"
                )

            comp_type = entry["comp_type"]
            byte_length = self._compute_byte_length(
                data_type, length, decimal_places, signed, comp_type
            )

            # Handle field name
            field_name = entry["name"]
            is_filler = field_name == "FILLER"
            if is_filler:
                filler_counter += 1
                field_name = f"FILLER_{filler_counter}"

            # Handle REDEFINES
            redefines_target = entry.get("redefines")
            start_pos = byte_offset

            if redefines_target:
                if redefines_target in redefines_positions:
                    start_pos = redefines_positions[redefines_target]
                else:
                    warnings.append(
                        f"Line {entry['line_number']}: REDEFINES target '{redefines_target}' "
                        f"not found, using current offset"
                    )

            # Handle OCCURS expansion
            occurs_count = entry["occurs"]
            if occurs_count > 1:
                for occ in range(1, occurs_count + 1):
                    occ_name = f"{field_name}_{occ}"
                    occ_start = start_pos + (occ - 1) * byte_length

                    field_def = FileFieldDefinition(
                        name=occ_name,
                        data_type=data_type,
                        length=length,
                        byte_length=byte_length,
                        start_position=occ_start,
                        decimal_places=decimal_places,
                        signed=signed,
                        comp_type=comp_type.value,
                        is_filler=is_filler,
                        redefines=redefines_target,
                        occurs=occurs_count,
                    )
                    fields.append(field_def)

                # Advance offset for all occurrences (unless REDEFINES)
                if not redefines_target:
                    redefines_positions[field_name] = start_pos
                    byte_offset = start_pos + byte_length * occurs_count
            else:
                field_def = FileFieldDefinition(
                    name=field_name,
                    data_type=data_type,
                    length=length,
                    byte_length=byte_length,
                    start_position=start_pos,
                    decimal_places=decimal_places,
                    signed=signed,
                    comp_type=comp_type.value,
                    is_filler=is_filler,
                    redefines=redefines_target,
                    occurs=1,
                )
                fields.append(field_def)

                # Track position for REDEFINES lookups
                redefines_positions[field_name] = start_pos

                # Advance offset only for non-REDEFINES fields
                if not redefines_target:
                    byte_offset += byte_length

        return fields

    def _parse_pic(self, pic: str) -> tuple[str, int, int, bool]:
        """Parse a PIC clause string into (data_type, length, decimal_places, signed).

        Returns:
            Tuple of (data_type, total_digit_length, decimal_places, is_signed).
        """
        pic = pic.strip().upper()

        signed = pic.startswith("S")
        if signed:
            pic = pic[1:]

        # Expand shorthand: X(10) -> XXXXXXXXXX, 9(5) -> 99999
        expanded = self._expand_pic(pic)

        # Validate: only allow recognized PIC characters (9, X, A, V, S, P)
        allowed = set("9XAVSP")
        invalid_chars = set(expanded) - allowed
        if invalid_chars:
            raise ValueError(
                f"Unrecognized PIC symbol(s): {', '.join(sorted(invalid_chars))}"
            )

        # Determine type and counts
        if "V" in expanded:
            # Decimal: digits before V + digits after V
            parts = expanded.split("V", 1)
            int_part = parts[0]
            dec_part = parts[1]

            int_digits = int_part.count("9")
            dec_digits = dec_part.count("9")

            return "decimal", int_digits + dec_digits, dec_digits, signed

        elif "X" in expanded or "A" in expanded:
            # Alphanumeric or alphabetic
            length = len(expanded)
            return "alphanumeric", length, 0, False

        elif "9" in expanded:
            # Numeric display
            digits = expanded.count("9")
            return "numeric", digits, 0, signed

        else:
            raise ValueError(f"Unrecognized PIC pattern: {pic}")

    def _expand_pic(self, pic: str) -> str:
        """Expand PIC shorthand notation: X(10) -> XXXXXXXXXX."""
        result = ""
        i = 0
        while i < len(pic):
            ch = pic[i]
            if i + 1 < len(pic) and pic[i + 1] == "(":
                # Find closing paren
                close = pic.index(")", i + 2)
                count = int(pic[i + 2 : close])
                result += ch * count
                i = close + 1
            else:
                result += ch
                i += 1
        return result

    def _compute_byte_length(
        self,
        data_type: str,
        length: int,
        decimal_places: int,
        signed: bool,
        comp_type: CompType,
    ) -> int:
        """Compute physical byte length based on data type and computational type.

        COMP-3 (packed decimal): ceil((total_digits + 1) / 2)
            Each digit = 1 nibble, sign = 1 nibble, packed into bytes.
            Example: S9(7)V99 = 9 digits + 1 sign nibble = 10 nibbles = 5 bytes.
            Example: 9(5) = 5 digits + 1 sign nibble = 6 nibbles = 3 bytes.

        COMP (binary): 1-4 digits=2 bytes, 5-9 digits=4 bytes, 10-18 digits=8 bytes.

        Display (no COMP): 1 byte per character/digit.
        """
        total_digits = length  # Includes integer + decimal digits

        if comp_type == CompType.COMP_3:
            # Packed decimal: each digit = 1 nibble, sign = 1 nibble
            nibbles = total_digits + 1  # +1 for sign nibble (always present)
            return math.ceil(nibbles / 2)

        elif comp_type == CompType.COMP:
            # Binary: byte length depends on digit count
            if total_digits <= 4:
                return 2
            elif total_digits <= 9:
                return 4
            else:
                return 8

        else:
            # Display format: 1 byte per character/digit
            if data_type == "alphanumeric":
                return length
            else:
                # Numeric display: each digit = 1 byte
                # Sign is embedded in trailing/leading byte (no extra byte)
                return total_digits
