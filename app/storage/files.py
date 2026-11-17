from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Protocol

_KEY_RE = re.compile(r"^[a-f0-9]{32}\.(jpg|png)$")


class FileStorage(Protocol):
    """Abstraction allowing an S3/object-storage backend to replace the local disk."""

    def save(self, key: str, data: bytes) -> None: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        # Keys are generated server-side; this strict check is defence in depth vs path traversal.
        if not _KEY_RE.fullmatch(key):
            raise ValueError("Invalid storage key")
        path = (self._root / key[:2] / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("Invalid storage key")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
