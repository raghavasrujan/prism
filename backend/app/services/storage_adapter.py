"""Local-filesystem storage adapter.

Interface mirrors what a future S3-backed impl will provide, so swap is a
one-file change.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.config import get_settings


@dataclass
class StoredFile:
    storage_path: str
    sha256: str
    size_bytes: int
    mime_type: str


class StorageAdapter(Protocol):
    def save(self, *, user_id: str, filename: str, data: bytes) -> StoredFile: ...
    def read(self, storage_path: str) -> bytes: ...
    def delete(self, storage_path: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str | None = None) -> None:
        self._root = Path(root or get_settings().upload_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, rel: str) -> Path:
        p = (self._root / rel).resolve()
        if not str(p).startswith(str(self._root)):
            raise ValueError("path traversal blocked")
        return p

    def save(self, *, user_id: str, filename: str, data: bytes) -> StoredFile:
        sha = hashlib.sha256(data).hexdigest()
        ext = Path(filename).suffix.lower() or ""
        now = datetime.now(timezone.utc)
        rel = f"{user_id}/{now.year:04d}/{now.month:02d}/{sha}{ext}"
        abs_path = self._resolve(rel)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(abs_path, "wb") as fh:
            fh.write(data)
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return StoredFile(
            storage_path=rel,
            sha256=sha,
            size_bytes=len(data),
            mime_type=mime,
        )

    def read(self, storage_path: str) -> bytes:
        abs_path = self._resolve(storage_path)
        with open(abs_path, "rb") as fh:
            return fh.read()

    def delete(self, storage_path: str) -> None:
        abs_path = self._resolve(storage_path)
        try:
            os.remove(abs_path)
        except FileNotFoundError:
            pass


def get_storage() -> StorageAdapter:
    return LocalStorage()
