"""Storage service: persists uploaded videos and analysis artifacts.

A thin ``Storage`` protocol with a filesystem implementation. Swapping in S3
later means writing one more class; nothing else in the app changes.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import get_settings


class Storage(Protocol):
    def save_upload(self, session_id: int, filename: str, fileobj: BinaryIO) -> str: ...
    def artifact_path(self, session_id: int, name: str) -> str: ...
    def open(self, path: str, mode: str = "rb") -> BinaryIO: ...
    def exists(self, path: str) -> bool: ...
    def delete(self, path: str) -> None: ...
    def delete_session(self, session_id: int) -> None: ...


class FileSystemStorage:
    """Stores everything under ``settings.storage_dir/sessions/<id>/``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or get_settings().storage_dir)

    def _session_dir(self, session_id: int) -> Path:
        d = self.root / "sessions" / str(session_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_upload(self, session_id: int, filename: str, fileobj: BinaryIO) -> str:
        safe = Path(filename).name or "video.mp4"
        dest = self._session_dir(session_id) / f"source_{safe}"
        with dest.open("wb") as out:
            shutil.copyfileobj(fileobj, out)
        return str(dest)

    def artifact_path(self, session_id: int, name: str) -> str:
        return str(self._session_dir(session_id) / name)

    def open(self, path: str, mode: str = "rb") -> BinaryIO:
        return open(path, mode)

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def delete(self, path: str) -> None:
        """Remove a single stored file (e.g. the source video). No-op if missing."""
        Path(path).unlink(missing_ok=True)

    def delete_session(self, session_id: int) -> None:
        """Remove a session's entire storage directory (video + all artifacts)."""
        shutil.rmtree(self.root / "sessions" / str(session_id), ignore_errors=True)


def get_storage() -> Storage:
    return FileSystemStorage()
