"""Unit tests for the cross-file relationship suggester."""

from __future__ import annotations

from app.domain.synthetic.file_schema import (
    FileFieldDefinition,
    FileSchemaDefinition,
)
from app.domain.synthetic.relationship_suggester import (
    suggest_relationships,
)


def _field(name: str, dtype: str = "numeric", length: int = 8, offset: int = 0):
    return FileFieldDefinition(
        name=name,
        data_type=dtype,
        length=length,
        byte_length=length,
        start_position=offset,
    )


def _schema(name: str, fields: list[FileFieldDefinition]) -> FileSchemaDefinition:
    return FileSchemaDefinition(name=name, fields=fields, file_format="csv")


def test_strong_name_match_scores_high():
    customers = _schema("CUSTOMERS", [_field("ID")])
    orders = _schema("ORDERS", [_field("CUSTOMER_ID")])
    out = suggest_relationships([orders, customers])

    # Both directions get scored — we expect the ORDERS.CUSTOMER_ID → CUSTOMERS.ID
    # suggestion to surface at the top because of the prefix-stripped name match
    # and identical numeric/length compatibility.
    top = out[0]
    assert {top.source_file, top.target_file} == {"ORDERS", "CUSTOMERS"}
    assert top.score > 0.7
    # Substring match on the raw names — ID is a substring of CUSTOMER_ID.
    # That registers as the strong-but-not-equal tier (0.85).
    assert top.evidence.name_similarity >= 0.85


def test_type_mismatch_lowers_score_significantly():
    a = _schema("A", [_field("X", "numeric", 8)])
    b = _schema("B", [_field("Y", "alphanumeric", 30)])
    out = suggest_relationships([a, b], min_score=0.0)
    pair = next(s for s in out if s.source_file == "A")
    assert pair.evidence.type_compatibility == 0.0
    # Without overlap or strong type match, the score should be pulled down.
    assert pair.score < 0.5


def test_value_overlap_is_used_when_samples_are_present():
    schemas = [
        _schema("CUSTOMERS", [_field("ID")]),
        _schema("ORDERS", [_field("CUSTOMER_ID")]),
    ]
    samples = {
        "CUSTOMERS": [{"ID": 1}, {"ID": 2}, {"ID": 3}],
        "ORDERS": [{"CUSTOMER_ID": 1}, {"CUSTOMER_ID": 2}],
    }
    out = suggest_relationships(schemas, samples=samples)
    top = next(
        s
        for s in out
        if s.source_file == "ORDERS" and s.target_file == "CUSTOMERS"
    )
    assert top.evidence.value_overlap is not None
    assert top.evidence.value_overlap > 0.9  # both child values are present in parent
    assert top.sample_size == 2  # min(len(child), len(parent)) — sample size hint


def test_min_score_filters_low_confidence():
    a = _schema("A", [_field("FOO")])
    b = _schema("B", [_field("BAR_THAT_LOOKS_UNRELATED")])
    high = suggest_relationships([a, b], min_score=0.9)
    assert high == []
    low = suggest_relationships([a, b], min_score=0.0)
    assert low != []


def test_self_pairs_are_skipped():
    a = _schema("A", [_field("ID"), _field("OTHER_ID")])
    out = suggest_relationships([a])
    # A only pairs with itself; the suggester must never return a self-pair.
    assert all(s.source_file != s.target_file for s in out)


def test_filler_fields_are_ignored():
    from dataclasses import replace

    a_fields = [_field("ID"), replace(_field("FILLER_1"), is_filler=True)]
    b = _schema("B", [_field("ID")])
    a = _schema("A", a_fields)
    out = suggest_relationships([a, b], min_score=0.0)
    for s in out:
        assert "FILLER" not in s.source_field
        assert "FILLER" not in s.target_field
