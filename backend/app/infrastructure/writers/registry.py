"""Writer registry — resolves FileFormat to writer class.

Default registry registers every writer in this package. Used by Phase 46's
orchestrator and surfaced to the frontend via GET /api/v1/file-formats.
"""

from __future__ import annotations

from app.domain.shared.errors import NotFoundError
from app.domain.synthetic.value_objects import FileFormat
from app.infrastructure.writers.base_writer import BaseFileWriter


class WriterRegistry:
    """FileFormat → writer class map."""

    def __init__(self) -> None:
        self._by_format: dict[FileFormat, type[BaseFileWriter]] = {}

    def register(self, writer_cls: type[BaseFileWriter]) -> None:
        for fmt in writer_cls.supported_formats():
            existing = self._by_format.get(fmt)
            if existing is not None and existing is not writer_cls:
                raise ValueError(
                    f"Format {fmt.value!r} already registered to {existing.__name__}; "
                    f"cannot also register {writer_cls.__name__}"
                )
            self._by_format[fmt] = writer_cls

    def get_writer(self, fmt: FileFormat) -> BaseFileWriter:
        cls = self._by_format.get(fmt)
        if cls is None:
            raise NotFoundError(
                message=f"No writer registered for format: {fmt.value}",
                code="writer_not_found",
            )
        return cls()

    def supported_formats(self) -> list[FileFormat]:
        return sorted(self._by_format.keys(), key=lambda f: f.value)


def create_default_registry() -> WriterRegistry:
    """Build a registry with every writer in this package registered once."""
    from app.infrastructure.writers.columnar_writer import ColumnarWriter
    from app.infrastructure.writers.csv_writer import CSVWriter
    from app.infrastructure.writers.fixed_width_writer import FixedWidthWriter
    from app.infrastructure.writers.vsam_writer import VSAMWriter

    registry = WriterRegistry()
    registry.register(CSVWriter)
    registry.register(FixedWidthWriter)
    registry.register(VSAMWriter)
    registry.register(ColumnarWriter)
    return registry


_singleton: WriterRegistry | None = None


def default_registry() -> WriterRegistry:
    """Module-level singleton (constructed lazily)."""
    global _singleton
    if _singleton is None:
        _singleton = create_default_registry()
    return _singleton


def get_writer(fmt: FileFormat) -> BaseFileWriter:
    """Shorthand: resolve a writer through the default registry."""
    return default_registry().get_writer(fmt)
