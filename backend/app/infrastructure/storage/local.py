"""Local filesystem storage backend with path traversal prevention."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.storage.base import StorageBackend


class LocalFilesystemStorage(StorageBackend):
    def __init__(self, base_dir: str = "/data/storage") -> None:
        self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, path: str) -> Path:
        """Resolve path and verify it stays within base_dir. Prevents path traversal."""
        if ".." in path:
            raise ValueError(f"Path traversal detected: {path}")
        resolved = (self._base_dir / path).resolve()
        if not str(resolved).startswith(str(self._base_dir)):
            raise ValueError(f"Path escapes base directory: {path}")
        return resolved

    async def save(self, path: str, data: bytes) -> str:
        full_path = self._safe_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)
        return str(full_path)

    async def load(self, path: str) -> bytes:
        full_path = self._safe_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return full_path.read_bytes()

    async def delete(self, path: str) -> None:
        full_path = self._safe_path(path)
        if full_path.exists():
            full_path.unlink()

    async def list(self, prefix: str = "") -> list[str]:
        search_dir = self._safe_path(prefix) if prefix else self._base_dir
        if not search_dir.is_dir():
            return []
        return [str(p.relative_to(self._base_dir)) for p in search_dir.rglob("*") if p.is_file()]

    async def get_url(self, path: str) -> str:
        full_path = self._safe_path(path)
        return f"file://{full_path}"
