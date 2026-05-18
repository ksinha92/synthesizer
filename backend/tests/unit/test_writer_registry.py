"""Unit tests for WriterRegistry."""

from __future__ import annotations

import pytest

from app.domain.shared.errors import NotFoundError
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.columnar_writer import ColumnarWriter
from app.infrastructure.writers.csv_writer import CSVWriter
from app.infrastructure.writers.fixed_width_writer import FixedWidthWriter
from app.infrastructure.writers.registry import (
    WriterRegistry,
    create_default_registry,
    default_registry,
    get_writer,
)
from app.infrastructure.writers.vsam_writer import VSAMWriter


def test_default_registry_has_all_formats():
    reg = create_default_registry()
    fmts = reg.supported_formats()
    assert len(fmts) == 6
    assert set(fmts) == set(FileFormat)


def test_get_writer_per_format():
    assert isinstance(get_writer(FileFormat.CSV), CSVWriter)
    assert isinstance(get_writer(FileFormat.FIXED_WIDTH), FixedWidthWriter)
    assert isinstance(get_writer(FileFormat.VSAM_FIXED), VSAMWriter)
    assert isinstance(get_writer(FileFormat.VSAM_VARIABLE), VSAMWriter)
    assert isinstance(get_writer(FileFormat.PARQUET), ColumnarWriter)
    assert isinstance(get_writer(FileFormat.ORC), ColumnarWriter)


def test_get_writer_unknown_raises_not_found():
    fresh = WriterRegistry()
    with pytest.raises(NotFoundError):
        fresh.get_writer(FileFormat.CSV)


def test_register_collision_raises():
    fresh = WriterRegistry()
    fresh.register(CSVWriter)

    class Fake:
        @classmethod
        def supported_formats(cls):
            return {FileFormat.CSV}

    with pytest.raises(ValueError, match="already registered"):
        fresh.register(Fake)


def test_factory_returns_fresh_instance():
    a = get_writer(FileFormat.CSV)
    b = get_writer(FileFormat.CSV)
    assert a is not b
    assert isinstance(a, CSVWriter)
    assert isinstance(b, CSVWriter)


def test_singleton_is_cached():
    a = default_registry()
    b = default_registry()
    assert a is b
