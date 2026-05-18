"""Writer base class and crash-safe write helper.

No format-specific imports live in this module — every concrete writer in
this package depends on this file, but never the other way around.
"""

from __future__ import annotations

import abc
import contextlib
import os
import uuid
from pathlib import Path
from typing import IO, Iterator

from app.domain.synthetic.file_schema import FileSchemaDefinition
from app.domain.synthetic.value_objects import FileFormat


class BaseFileWriter(abc.ABC):
    """Contract every file writer implements.

    Writers are sync — the calling Celery task is the async layer. Each
    writer must:
      - declare which FileFormat values it handles via `supported_formats`
      - serialize rows to bytes/text using the schema as the source of truth
      - emit output through `write_atomic` so a partially-written file
        never becomes visible at `output_path`.
    """

    @abc.abstractmethod
    def write(
        self,
        schema: FileSchemaDefinition,
        rows: list[dict],
        output_path: Path,
    ) -> Path:
        """Write `rows` for `schema` to `output_path`. Returns the path written."""

    @abc.abstractmethod
    def get_extension(self) -> str:
        """File extension (without dot) for this writer's format."""

    @classmethod
    @abc.abstractmethod
    def supported_formats(cls) -> set[FileFormat]:
        """FileFormat values this writer handles."""

    # ── Concrete helpers shared by every writer ───────────────────────────

    def validate_schema(self, schema: FileSchemaDefinition) -> list[str]:
        """Return schema validation errors. Delegates to the domain."""
        return schema.validate()

    def _ensure_writable(
        self,
        schema: FileSchemaDefinition,
        rows: list[dict],
        output_path: Path,
    ) -> None:
        """Reject before opening any file handle.

        Raises:
            ValueError: schema fails domain validation.
            FileNotFoundError: parent directory does not exist.
        """
        errors = self.validate_schema(schema)
        if errors:
            raise ValueError("Schema validation failed: " + "; ".join(errors))
        if not output_path.parent.exists():
            raise FileNotFoundError(
                f"Parent directory does not exist: {output_path.parent}"
            )


@contextlib.contextmanager
def write_atomic(output_path: Path, mode: str = "wb") -> Iterator[IO]:
    """Write to a sibling temp file then atomically rename on success.

    On clean exit: flush + fsync the temp file, then os.replace() onto
    output_path. On exception: close the handle, unlink the temp file, and
    re-raise — output_path is never observable in a half-written state.
    """
    tmp_path = output_path.parent / f".{output_path.name}.tmp.{uuid.uuid4().hex}"
    handle = open(tmp_path, mode)
    try:
        yield handle
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except (OSError, AttributeError):
            # fsync may fail on non-regular files / unusual filesystems —
            # the os.replace below is still atomic w.r.t. observers.
            pass
        handle.close()
        os.replace(tmp_path, output_path)
    except BaseException:
        try:
            handle.close()
        except Exception:
            pass
        tmp_path.unlink(missing_ok=True)
        raise
