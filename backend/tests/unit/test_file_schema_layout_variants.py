"""Unit tests for the multi-record-layout extensions to FileSchemaDefinition."""

from __future__ import annotations

import pytest

from app.domain.synthetic.file_schema import (
    FileFieldDefinition,
    FileSchemaDefinition,
    LayoutCondition,
    LayoutVariant,
)


def _field(name: str, offset: int = 0, length: int = 8, dtype: str = "alphanumeric"):
    return FileFieldDefinition(
        name=name,
        data_type=dtype,
        length=length,
        byte_length=length,
        start_position=offset,
    )


class TestLayoutCondition:
    def test_eq_matches_string(self):
        c = LayoutCondition(field_name="RECORD_TYPE", operator="eq", value="H")
        assert c.evaluate("H") is True
        assert c.evaluate("D") is False

    def test_eq_ignores_padding_whitespace(self):
        c = LayoutCondition(field_name="RT", operator="eq", value="H")
        assert c.evaluate("  H  ") is True

    def test_in_membership_with_tuple(self):
        c = LayoutCondition(field_name="RT", operator="in", value=("H", "T"))
        assert c.evaluate("H") is True
        assert c.evaluate("T") is True
        assert c.evaluate("D") is False

    def test_in_membership_from_round_trip(self):
        c = LayoutCondition.from_dict(
            {"field_name": "RT", "operator": "in", "value": ["A", "B"]}
        )
        assert c.evaluate("A") is True
        assert c.evaluate("Z") is False

    def test_starts_with_matches_prefix(self):
        c = LayoutCondition(field_name="ID", operator="starts_with", value="CUST")
        assert c.evaluate("CUST-100") is True
        assert c.evaluate("ORDR-1") is False

    def test_none_value_never_matches(self):
        c = LayoutCondition(field_name="RT", operator="eq", value="H")
        assert c.evaluate(None) is False


class TestLayoutVariant:
    def test_matches_all_conditions(self):
        v = LayoutVariant(
            name="Header",
            fields=[_field("X")],
            conditions=[
                LayoutCondition(field_name="RT", operator="eq", value="H"),
                LayoutCondition(field_name="ENV", operator="in", value=("PROD", "STG")),
            ],
        )
        assert v.matches({"RT": "H", "ENV": "PROD"}) is True
        # Missing one condition → no match.
        assert v.matches({"RT": "H", "ENV": "DEV"}) is False

    def test_empty_conditions_never_match(self):
        # Variants without discriminators are valid (the wizard might
        # save them mid-edit), but they must not silently capture rows.
        v = LayoutVariant(name="Headerless", fields=[_field("X")], conditions=[])
        assert v.matches({"RT": "H"}) is False

    def test_round_trip(self):
        v = LayoutVariant(
            name="Detail",
            fields=[_field("AMOUNT", offset=10, length=8, dtype="numeric")],
            conditions=[LayoutCondition(field_name="RT", operator="eq", value="D")],
        )
        out = LayoutVariant.from_dict(v.to_dict())
        assert out.name == "Detail"
        assert len(out.fields) == 1
        assert out.fields[0].name == "AMOUNT"
        assert out.conditions[0].operator == "eq"


class TestFileSchemaDefinitionVariants:
    def test_select_variant_returns_first_match(self):
        schema = FileSchemaDefinition(
            name="multi",
            fields=[_field("RT", 0, 1)],
            file_format="fixed_width",
            layout_variants=[
                LayoutVariant(
                    name="Header",
                    fields=[_field("HEAD_FIELD")],
                    conditions=[LayoutCondition("RT", "eq", "H")],
                ),
                LayoutVariant(
                    name="Detail",
                    fields=[_field("DET_FIELD")],
                    conditions=[LayoutCondition("RT", "eq", "D")],
                ),
            ],
        )
        assert schema.select_variant({"RT": "H"}).name == "Header"
        assert schema.select_variant({"RT": "D"}).name == "Detail"
        assert schema.select_variant({"RT": "X"}) is None

    def test_to_dict_round_trips_variants(self):
        schema = FileSchemaDefinition(
            name="multi",
            fields=[_field("RT", 0, 1)],
            file_format="fixed_width",
            layout_variants=[
                LayoutVariant(
                    name="Header",
                    fields=[_field("HEAD_FIELD")],
                    conditions=[LayoutCondition("RT", "eq", "H")],
                ),
            ],
        )
        out = FileSchemaDefinition.from_dict(schema.to_dict())
        assert len(out.layout_variants) == 1
        assert out.layout_variants[0].name == "Header"
        assert out.layout_variants[0].conditions[0].operator == "eq"

    def test_legacy_metadata_round_trip(self):
        """from_dict reads layout_variants from metadata when top-level is missing.

        Schemas saved before this field reached the SQL column shape store
        it under metadata.layout_variants. The deserializer must still
        find them so old projects keep working without a migration.
        """
        legacy = {
            "name": "multi",
            "fields": [_field("RT", 0, 1).to_dict()],
            "file_format": "fixed_width",
            "metadata": {
                "layout_variants": [
                    {
                        "name": "Header",
                        "fields": [_field("HEAD_FIELD").to_dict()],
                        "conditions": [
                            {"field_name": "RT", "operator": "eq", "value": "H"}
                        ],
                    }
                ]
            },
        }
        schema = FileSchemaDefinition.from_dict(legacy)
        assert len(schema.layout_variants) == 1
        assert schema.layout_variants[0].name == "Header"

    def test_empty_variants_preserves_single_layout_behavior(self):
        schema = FileSchemaDefinition(
            name="single",
            fields=[_field("X")],
            file_format="csv",
        )
        assert schema.layout_variants == []
        assert schema.select_variant({"X": "anything"}) is None


class TestCopybookParserSplitStrategies:
    """End-to-end: parse a small multi-01 copybook with each strategy."""

    COPYBOOK = """\
       01 HEADER-REC.
          05 RECORD-TYPE     PIC X(1).
          05 BATCH-ID        PIC 9(5).
       01 DETAIL-REC.
          05 RECORD-TYPE     PIC X(1).
          05 ORDER-NUM       PIC 9(6).
          05 AMOUNT          PIC S9(5)V99 COMP-3.
"""

    def test_single_strategy_flattens(self):
        from app.infrastructure.parsers.copybook_parser import (
            CopybookParser,
            SplitStrategy,
        )

        parser = CopybookParser()
        schema = parser.parse(self.COPYBOOK, split_strategy=SplitStrategy.SINGLE)
        # All non-group fields end up in one flat list.
        assert any(f.name == "RECORD-TYPE" for f in schema.fields)
        assert any(f.name == "AMOUNT" for f in schema.fields)
        assert schema.layout_variants == []

    def test_split_01_emits_one_variant_per_extra_01(self):
        from app.infrastructure.parsers.copybook_parser import (
            CopybookParser,
            SplitStrategy,
        )

        parser = CopybookParser()
        schema = parser.parse(self.COPYBOOK, split_strategy=SplitStrategy.SPLIT_01_LEVEL)
        # Base layout = first 01; one variant for the second 01.
        assert len(schema.layout_variants) == 1
        assert schema.layout_variants[0].name == "DETAIL-REC"
        # The base must not carry detail fields.
        base_names = {f.name for f in schema.fields}
        assert "ORDER-NUM" not in base_names
        # Variant carries them.
        variant_names = {f.name for f in schema.layout_variants[0].fields}
        assert "ORDER-NUM" in variant_names
        assert "AMOUNT" in variant_names

    def test_split_01_falls_back_to_single_when_only_one_01(self):
        from app.infrastructure.parsers.copybook_parser import (
            CopybookParser,
            SplitStrategy,
        )

        cpy = "       01 SINGLE-REC.\n          05 X PIC X(5)."
        parser = CopybookParser()
        schema = parser.parse(cpy, split_strategy=SplitStrategy.SPLIT_01_LEVEL)
        assert schema.layout_variants == []
        assert any(f.name == "X" for f in schema.fields)
