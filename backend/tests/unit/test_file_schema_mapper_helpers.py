"""Unit tests for the dictionary-mapper helper that powers POST + PATCH.

Both the create endpoint (``POST /derive``) and the re-edit endpoint
(``PATCH /mapping``) build their target field list from
``_build_target_fields`` — tests live here so adding a new transform
doesn't silently break one of the two paths.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.v1.file_schema_mapper import (
    DeriveSchemaRequest,
    MappingSpec,
    TransformSpec,
    _build_target_fields,
)
from app.domain.synthetic.file_schema import FileFieldDefinition


def _src_field(name: str, length: int = 8, dtype: str = "alphanumeric"):
    return FileFieldDefinition(
        name=name,
        data_type=dtype,
        length=length,
        byte_length=length,
        start_position=0,
    )


def _req(mappings: list[MappingSpec]) -> DeriveSchemaRequest:
    return DeriveSchemaRequest(
        target_name="TARGET",
        target_format="csv",
        target_encoding="utf8",
        mappings=mappings,
    )


def test_1to1_mapping_inherits_source_type_and_length():
    src = {"CUSTOMER_NAME": _src_field("CUSTOMER_NAME", length=30)}
    out = _build_target_fields(
        _req([MappingSpec(target_field="CUST_NM", source_field="CUSTOMER_NAME")]),
        src,
    )
    assert len(out) == 1
    assert out[0].name == "CUST_NM"
    assert out[0].data_type == "alphanumeric"
    assert out[0].length == 30
    assert out[0].byte_length == 30
    assert out[0].start_position == 0


def test_pad_transform_extends_length():
    src = {"NAME": _src_field("NAME", length=10)}
    out = _build_target_fields(
        _req(
            [
                MappingSpec(
                    target_field="NAME_PADDED",
                    source_field="NAME",
                    transforms=[TransformSpec(type="pad", args={"length": 30, "side": "right", "char": " "})],
                )
            ]
        ),
        src,
    )
    assert out[0].length == 30
    assert out[0].byte_length == 30


def test_substring_transform_shrinks_length():
    src = {"PHONE": _src_field("PHONE", length=15)}
    out = _build_target_fields(
        _req(
            [
                MappingSpec(
                    target_field="AREA_CODE",
                    source_field="PHONE",
                    transforms=[TransformSpec(type="substring", args={"start": 0, "end": 3})],
                )
            ]
        ),
        src,
    )
    assert out[0].length == 3
    assert out[0].byte_length == 3


def test_constant_mapping_with_no_source_field():
    src: dict[str, FileFieldDefinition] = {}
    out = _build_target_fields(
        _req(
            [
                MappingSpec(
                    target_field="ENV_FLAG",
                    source_field=None,
                    constant="PROD",
                )
            ]
        ),
        src,
    )
    assert out[0].name == "ENV_FLAG"
    assert out[0].data_type == "alphanumeric"
    assert out[0].length == 4  # len("PROD")


def test_duplicate_target_field_is_rejected():
    src = {"X": _src_field("X")}
    with pytest.raises(HTTPException) as ei:
        _build_target_fields(
            _req(
                [
                    MappingSpec(target_field="OUT", source_field="X"),
                    MappingSpec(target_field="OUT", source_field="X"),
                ]
            ),
            src,
        )
    assert ei.value.status_code == 400
    assert ei.value.detail["error"] == "duplicate_target_field"


def test_unknown_source_field_is_rejected():
    src = {"X": _src_field("X")}
    with pytest.raises(HTTPException) as ei:
        _build_target_fields(
            _req([MappingSpec(target_field="OUT", source_field="DOES_NOT_EXIST")]),
            src,
        )
    assert ei.value.status_code == 400
    assert ei.value.detail["error"] == "unknown_source_field"


def test_offsets_chain_across_multiple_fields():
    src = {"A": _src_field("A", length=4), "B": _src_field("B", length=6)}
    out = _build_target_fields(
        _req(
            [
                MappingSpec(target_field="TA", source_field="A"),
                MappingSpec(target_field="TB", source_field="B"),
            ]
        ),
        src,
    )
    assert out[0].start_position == 0
    assert out[1].start_position == 4  # advanced by A's byte_length
