"""Zip bundle for multi-file generation output.

Wraps a list of written files plus a JSON manifest into a single zip archive,
written atomically via `write_atomic`.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Iterable

from app.infrastructure.writers.base_writer import write_atomic


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bundle_files(
    files: Iterable[Path],
    manifest: dict,
    output_path: Path,
    compression: int = zipfile.ZIP_DEFLATED,
) -> Path:
    """Produce a zip at `output_path` containing every file plus manifest.json.

    `manifest` is mutated: a `files` list is added with per-file
    {name, byte_count, sha256}.
    """
    files = list(files)
    manifest = dict(manifest)
    entries = []

    # Pre-read so we can hash + size before writing the zip.
    payloads = []
    for f in files:
        data = Path(f).read_bytes()
        payloads.append((Path(f).name, data))
        entries.append(
            {
                "name": Path(f).name,
                "byte_count": len(data),
                "sha256": _sha256(data),
            }
        )
    manifest["files"] = entries

    with write_atomic(output_path, mode="wb") as handle:
        with zipfile.ZipFile(handle, mode="w", compression=compression) as zf:
            for name, data in payloads:
                zf.writestr(name, data)
            zf.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, default=str, sort_keys=True),
            )

    return output_path
