"""File schema domain model for file-based synthetic data generation. No framework dependencies."""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field


# File-schema fields don't live in ``discovered_columns``, so masking rules
# identify them via a deterministic UUID5 of (schema_id, field_name). The
# same input always maps to the same id — masking rules survive schema
# re-uploads, and the worker can build a reverse map to resolve
# ``linked_column_ids`` back to field names for joint generation.
FILE_COLUMN_NAMESPACE = _uuid.UUID("8a4f5d12-d8b7-4f7a-9c8e-6a3c1e9b2d44")


def file_field_column_id(schema_id: str, field_name: str) -> _uuid.UUID:
    """Stable synthetic column id for a (file schema, field) pair."""
    return _uuid.uuid5(FILE_COLUMN_NAMESPACE, f"{schema_id}::{field_name}")


@dataclass(frozen=True)
class FileFieldDefinition:
    """Definition of a single field within a file schema."""

    name: str
    data_type: str  # "alphanumeric", "numeric", "decimal", "binary", "packed_decimal"
    length: int  # Display/logical length in characters/digits
    byte_length: int  # Physical storage bytes (differs for COMP/COMP-3)
    start_position: int  # 0-based byte offset in record
    decimal_places: int = 0
    signed: bool = False
    comp_type: str = "none"  # Store as string for serialization; matches CompType values
    nullable: bool = True
    pii_type: str | None = None
    fk_reference: tuple | None = None  # (file, field) tuple — frozen-compatible
    is_filler: bool = False
    redefines: str | None = None  # Name of field being redefined
    occurs: int = 1

    def to_dict(self) -> dict:
        """Serialize to a plain JSON-compatible dict."""
        result = {
            "name": self.name,
            "data_type": self.data_type,
            "length": self.length,
            "byte_length": self.byte_length,
            "start_position": self.start_position,
            "decimal_places": self.decimal_places,
            "signed": self.signed,
            "comp_type": self.comp_type,
            "nullable": self.nullable,
            "pii_type": self.pii_type,
            "fk_reference": {"file": self.fk_reference[0], "field": self.fk_reference[1]} if self.fk_reference else None,
            "is_filler": self.is_filler,
            "redefines": self.redefines,
            "occurs": self.occurs,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> FileFieldDefinition:
        """Deserialize from a plain dict."""
        fk_ref = data.get("fk_reference")
        if fk_ref and isinstance(fk_ref, dict):
            fk_ref = (fk_ref["file"], fk_ref["field"])
        elif fk_ref and isinstance(fk_ref, (list, tuple)):
            fk_ref = tuple(fk_ref)
        else:
            fk_ref = None

        return cls(
            name=data["name"],
            data_type=data["data_type"],
            length=data["length"],
            byte_length=data["byte_length"],
            start_position=data["start_position"],
            decimal_places=data.get("decimal_places", 0),
            signed=data.get("signed", False),
            comp_type=data.get("comp_type", "none"),
            nullable=data.get("nullable", True),
            pii_type=data.get("pii_type"),
            fk_reference=fk_ref,
            is_filler=data.get("is_filler", False),
            redefines=data.get("redefines"),
            occurs=data.get("occurs", 1),
        )


@dataclass(frozen=True)
class LayoutCondition:
    """A single rule used to pick a LayoutVariant for a given record.

    Multi-record-layout copybooks (File-AID / Microfocus style) need a way
    to say "this record uses layout X when ``RECORD_TYPE = 'H'``." A
    LayoutCondition expresses one such test. A variant matches a record
    when ALL of its conditions match (AND semantics) — callers compose
    OR by registering multiple variants.
    """

    field_name: str          # name of a field on the BASE layout
    operator: str            # "eq" | "ne" | "in" | "starts_with"
    # Scalar for eq/ne/starts_with; tuple of strings for "in" (must be
    # hashable because the parent dataclass is frozen).
    value: str | tuple[str, ...]

    def evaluate(self, record_value: object) -> bool:
        """Test the condition against a single field value from a record."""
        if record_value is None:
            return False
        rv = str(record_value).strip()
        if self.operator == "eq":
            return rv == str(self.value)
        if self.operator == "ne":
            return rv != str(self.value)
        if self.operator == "starts_with":
            return rv.startswith(str(self.value))
        if self.operator == "in":
            options = self.value if isinstance(self.value, tuple) else (str(self.value),)
            return rv in {str(v) for v in options}
        return False

    def to_dict(self) -> dict:
        v = list(self.value) if isinstance(self.value, tuple) else self.value
        return {"field_name": self.field_name, "operator": self.operator, "value": v}

    @classmethod
    def from_dict(cls, data: dict) -> LayoutCondition:
        v = data["value"]
        if isinstance(v, list):
            v = tuple(str(x) for x in v)
        return cls(field_name=data["field_name"], operator=data["operator"], value=v)


@dataclass
class LayoutVariant:
    """A conditional record layout — selected when its conditions match.

    Single-layout schemas (today's behavior) leave ``layout_variants``
    empty on the parent ``FileSchemaDefinition``. When variants are
    present, the parent's ``fields`` list is the BASE layout (used to
    locate the discriminator field) and each variant's ``fields`` list
    is the full record interpretation chosen when its conditions match.
    """

    name: str
    fields: list[FileFieldDefinition]
    conditions: list[LayoutCondition] = field(default_factory=list)

    def matches(self, record: dict) -> bool:
        """True if every condition holds against ``record`` (AND semantics)."""
        if not self.conditions:
            return False
        return all(c.evaluate(record.get(c.field_name)) for c in self.conditions)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "fields": [f.to_dict() for f in self.fields],
            "conditions": [c.to_dict() for c in self.conditions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> LayoutVariant:
        return cls(
            name=data["name"],
            fields=[FileFieldDefinition.from_dict(f) for f in data.get("fields", [])],
            conditions=[LayoutCondition.from_dict(c) for c in data.get("conditions", [])],
        )


@dataclass
class FileSchemaDefinition:
    """Unified schema definition that all schema sources produce and all file writers consume."""

    name: str
    fields: list[FileFieldDefinition]
    file_format: str  # Store as string; matches FileFormat values
    encoding: str = "ascii"  # Matches EncodingType values
    record_length: int = 0  # Computed from fields if 0
    has_rdw: bool = False  # Record Descriptor Word for VSAM variable
    output_filename: str | None = None
    metadata: dict = field(default_factory=dict)
    # Optional File-AID-style conditional layouts. Empty list → schema is
    # single-layout (existing behavior preserved bit-for-bit).
    layout_variants: list[LayoutVariant] = field(default_factory=list)

    def select_variant(self, record: dict) -> LayoutVariant | None:
        """Return the first variant whose conditions match the record, or None.

        Callers fall back to the base ``fields`` list when this returns None.
        Order matters — earlier variants win when multiple could match.
        """
        for variant in self.layout_variants:
            if variant.matches(record):
                return variant
        return None

    def compute_record_length(self) -> int:
        """Sum of byte_lengths for all non-REDEFINES fields."""
        return sum(f.byte_length for f in self.fields if f.redefines is None)

    def get_field_by_name(self, name: str) -> FileFieldDefinition | None:
        """Look up a field by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def validate(self) -> list[str]:
        """Validate schema consistency. Returns list of error/warning strings."""
        errors: list[str] = []

        # Check byte_length > 0 for all fields
        for f in self.fields:
            if f.byte_length <= 0:
                errors.append(f"Field '{f.name}' has byte_length={f.byte_length} (must be > 0)")

        # Check duplicate non-filler field names
        non_filler_names: list[str] = []
        for f in self.fields:
            if not f.is_filler:
                if f.name in non_filler_names:
                    errors.append(f"Duplicate field name '{f.name}'")
                non_filler_names.append(f.name)

        # Check position overlaps (excluding REDEFINES fields)
        non_redefines = [f for f in self.fields if f.redefines is None]
        non_redefines_sorted = sorted(non_redefines, key=lambda f: f.start_position)
        for i in range(len(non_redefines_sorted) - 1):
            current = non_redefines_sorted[i]
            next_field = non_redefines_sorted[i + 1]
            current_end = current.start_position + current.byte_length
            if current_end > next_field.start_position:
                errors.append(
                    f"Position overlap: '{current.name}' ends at byte {current_end} "
                    f"but '{next_field.name}' starts at byte {next_field.start_position}"
                )

        # Check record_length consistency
        computed = self.compute_record_length()
        if self.record_length > 0 and self.record_length != computed:
            errors.append(
                f"Record length mismatch: stored={self.record_length}, computed={computed}"
            )

        # Format/encoding compatibility warning
        vsam_formats = ("vsam_fixed", "vsam_variable")
        ebcdic_encodings = ("ebcdic_cp037", "ebcdic_cp1140")
        if self.file_format in vsam_formats and self.encoding not in ebcdic_encodings:
            errors.append(
                f"Warning: VSAM format '{self.file_format}' typically uses EBCDIC encoding, "
                f"but encoding is '{self.encoding}'"
            )

        return errors

    def to_dict(self) -> dict:
        """Serialize to a plain JSON-compatible dict."""
        return {
            "name": self.name,
            "fields": [f.to_dict() for f in self.fields],
            "file_format": self.file_format,
            "encoding": self.encoding,
            "record_length": self.record_length,
            "has_rdw": self.has_rdw,
            "output_filename": self.output_filename,
            "metadata": self.metadata,
            "layout_variants": [v.to_dict() for v in self.layout_variants],
        }

    @classmethod
    def from_dict(cls, data: dict) -> FileSchemaDefinition:
        """Deserialize from a plain dict.

        Supports two storage shapes for ``layout_variants``: a top-level key
        (preferred — what ``to_dict`` emits) and a legacy nested key under
        ``metadata.layout_variants``. The legacy shape exists so schemas
        saved before this field reached the SQLAlchemy column shape still
        round-trip cleanly.
        """
        fields = [FileFieldDefinition.from_dict(f) for f in data.get("fields", [])]
        metadata = data.get("metadata") or {}
        raw_variants = data.get("layout_variants")
        if raw_variants is None:
            raw_variants = metadata.get("layout_variants") or []
        variants = [LayoutVariant.from_dict(v) for v in raw_variants]
        return cls(
            name=data["name"],
            fields=fields,
            file_format=data["file_format"],
            encoding=data.get("encoding", "ascii"),
            record_length=data.get("record_length", 0),
            has_rdw=data.get("has_rdw", False),
            output_filename=data.get("output_filename"),
            metadata=metadata,
            layout_variants=variants,
        )


@dataclass(frozen=True)
class CrossFileFK:
    """Foreign key relationship between two file schemas."""

    source_file: str  # Schema name
    source_field: str
    target_file: str  # Schema name
    target_field: str

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "source_field": self.source_field,
            "target_file": self.target_file,
            "target_field": self.target_field,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CrossFileFK:
        return cls(
            source_file=data["source_file"],
            source_field=data["source_field"],
            target_file=data["target_file"],
            target_field=data["target_field"],
        )


@dataclass
class FileSetDefinition:
    """A set of file schemas with cross-file FK relationships for multi-file generation."""

    name: str
    schemas: list[FileSchemaDefinition]
    foreign_keys: list[CrossFileFK] = field(default_factory=list)

    def get_schema_by_name(self, name: str) -> FileSchemaDefinition | None:
        """Look up a schema by name."""
        for s in self.schemas:
            if s.name == name:
                return s
        return None

    def validate(self) -> list[str]:
        """Validate file set consistency. Returns list of error strings."""
        errors: list[str] = []

        # Validate each schema
        for schema in self.schemas:
            schema_errors = schema.validate()
            for e in schema_errors:
                errors.append(f"[{schema.name}] {e}")

        # Check duplicate schema names
        schema_names = [s.name for s in self.schemas]
        seen: set[str] = set()
        for name in schema_names:
            if name in seen:
                errors.append(f"Duplicate schema name '{name}'")
            seen.add(name)

        # Validate FK references
        for fk in self.foreign_keys:
            source_schema = self.get_schema_by_name(fk.source_file)
            if not source_schema:
                errors.append(
                    f"FK source file '{fk.source_file}' not found in file set"
                )
            elif not source_schema.get_field_by_name(fk.source_field):
                errors.append(
                    f"FK source field '{fk.source_field}' not found in schema '{fk.source_file}'"
                )

            target_schema = self.get_schema_by_name(fk.target_file)
            if not target_schema:
                errors.append(
                    f"FK target file '{fk.target_file}' not found in file set"
                )
            elif not target_schema.get_field_by_name(fk.target_field):
                errors.append(
                    f"FK target field '{fk.target_field}' not found in schema '{fk.target_file}'"
                )

        return errors

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "schemas": [s.to_dict() for s in self.schemas],
            "foreign_keys": [fk.to_dict() for fk in self.foreign_keys],
        }

    @classmethod
    def from_dict(cls, data: dict) -> FileSetDefinition:
        schemas = [FileSchemaDefinition.from_dict(s) for s in data.get("schemas", [])]
        fks = [CrossFileFK.from_dict(fk) for fk in data.get("foreign_keys", [])]
        return cls(
            name=data["name"],
            schemas=schemas,
            foreign_keys=fks,
        )
