"""Tests for the zip bundler."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from app.infrastructure.writers.zip_bundler import bundle_files


def _make_file(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def test_bundle_files_contains_payloads_and_manifest(tmp_path):
    a = _make_file(tmp_path / "a.csv", "id,name\n1,Alice\n")
    b = _make_file(tmp_path / "b.txt", "hello world")
    out = tmp_path / "bundle.zip"
    bundle_files([a, b], {"file_set": "demo"}, out)

    with zipfile.ZipFile(out, "r") as zf:
        names = zf.namelist()
        assert "a.csv" in names
        assert "b.txt" in names
        assert "manifest.json" in names
        manifest = json.loads(zf.read("manifest.json"))

    assert manifest["file_set"] == "demo"
    entries_by_name = {e["name"]: e for e in manifest["files"]}
    assert entries_by_name["a.csv"]["byte_count"] == a.stat().st_size
    assert entries_by_name["a.csv"]["sha256"] == hashlib.sha256(a.read_bytes()).hexdigest()


def test_bundle_atomic_on_exception(tmp_path, monkeypatch):
    import zipfile as zf_module

    a = _make_file(tmp_path / "a.txt", "hi")
    out = tmp_path / "bundle.zip"

    real_writestr = zf_module.ZipFile.writestr

    def boom(self, name, data):
        if name == "manifest.json":
            raise RuntimeError("simulated failure")
        return real_writestr(self, name, data)

    monkeypatch.setattr(zf_module.ZipFile, "writestr", boom)

    with pytest.raises(RuntimeError, match="simulated"):
        bundle_files([a], {"x": 1}, out)

    assert not out.exists()
    assert list(tmp_path.glob(".bundle.zip.tmp.*")) == []
