"""Unit tests for the File Viewer tab's synthetic column-id derivation."""

from __future__ import annotations

import uuid

from app.api.v1.file_schema_view import _field_column_id


def test_field_column_id_is_deterministic():
    schema_id = "11111111-1111-1111-1111-111111111111"
    a = _field_column_id(schema_id, "customer_name")
    b = _field_column_id(schema_id, "customer_name")
    assert a == b
    # Different field → different id.
    c = _field_column_id(schema_id, "customer_address")
    assert a != c
    # Different schema → different id even for same field name.
    d = _field_column_id("22222222-2222-2222-2222-222222222222", "customer_name")
    assert a != d


def test_field_column_id_is_uuid5_namespaced():
    # Sanity check: derived ids are valid UUIDs and v5.
    out = _field_column_id("11111111-1111-1111-1111-111111111111", "field")
    assert isinstance(out, uuid.UUID)
    assert out.version == 5
