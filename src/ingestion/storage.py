"""Persists raw uploaded submission files to local disk so ingestion (including
OCR/vision calls) can be safely retried later without requiring the applicant
to re-upload - e.g. after fixing a broken Ollama connection.

Restricted/sensitive data must stay local: files are written under
UPLOAD_STORAGE_DIR (default ./data/uploads, gitignored), never uploaded
elsewhere.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _upload_root() -> Path:
    return Path(os.getenv("UPLOAD_STORAGE_DIR", "./data/uploads"))


def _safe_filename(name: str) -> str:
    # Path(...).name strips any directory components - the path-traversal guard.
    name = Path(name).name
    return _SAFE_NAME_RE.sub("_", name) or "upload"


def save_uploaded_files(scheme_id: int, submission_id: int, files: list[tuple[str, bytes]]) -> list[dict]:
    """Write each uploaded file to a per-scheme/per-submission folder on disk; returns a
    manifest (original filename + stored path + size) to persist alongside the submission."""
    if not files:
        return []
    folder = _upload_root() / str(scheme_id) / str(submission_id)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, (filename, content) in enumerate(files):
        stored_path = folder / f"{index:03d}_{_safe_filename(filename)}"
        stored_path.write_bytes(content)
        manifest.append({"filename": filename, "stored_path": str(stored_path), "size": len(content)})
    return manifest


def load_uploaded_files(raw_files: list[dict]) -> list[tuple[str, bytes]]:
    """Read previously-saved raw files back from disk for re-ingestion (e.g. retrying OCR)."""
    loaded = []
    for entry in raw_files:
        path = Path(entry["stored_path"])
        if not path.exists():
            raise FileNotFoundError(f"Stored upload missing: {path}")
        loaded.append((entry["filename"], path.read_bytes()))
    return loaded
