"""GET /api/v1/file-formats — supported writer formats for the synthetic UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.infrastructure.auth.dependencies import get_current_user
from app.infrastructure.writers.registry import default_registry

router = APIRouter(prefix="", tags=["file-formats"])


_LABELS = {
    "csv": "CSV",
    "fixed_width": "Fixed-width",
    "vsam_fixed": "VSAM Fixed",
    "vsam_variable": "VSAM Variable",
    "parquet": "Parquet",
    "orc": "ORC",
}

_EXTENSIONS = {
    "csv": "csv",
    "fixed_width": "txt",
    "vsam_fixed": "vsam",
    "vsam_variable": "vsam",
    "parquet": "parquet",
    "orc": "orc",
}


@router.get("/file-formats")
async def list_file_formats(current_user: dict = Depends(get_current_user)):
    """Return the writer-registry-derived list of supported file output formats."""
    registry = default_registry()
    formats = []
    for fmt in registry.supported_formats():
        writer = registry.get_writer(fmt)
        formats.append(
            {
                "value": fmt.value,
                "label": _LABELS.get(fmt.value, fmt.value),
                "extension": _EXTENSIONS.get(fmt.value, writer.get_extension()),
                "writer": writer.__class__.__name__,
            }
        )
    return {"formats": formats}
