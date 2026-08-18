"""Local-filesystem implementation of the ``Storage`` protocol.

Used for local development and tests. On Render this is **ephemeral** — the
container filesystem is wiped on every deploy and restart — so production uses
``SupabaseStorage``; here the filesystem only ever holds temp files for the CV
pipeline.

Keys are relative (``sessions/12/artifacts/landmarks.npz``) and resolved under
``storage_dir``. Every key is validated and the resolved path re-checked against
the root, so a crafted reference can't read or write outside it.
"""
from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings
from app.services.storage.keys import (
    UnsafeKeyError,
    artifact_key,
    normalize_reference,
    session_prefix,
    upload_key,
)


class FileSystemStorage:
    """Stores everything under ``settings.storage_dir/sessions/<id>/``."""

    name = "filesystem"

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or get_settings().storage_dir)

    # --- key handling ------------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """Key (or legacy absolute path) -> an absolute path inside ``root``."""
        rel = normalize_reference(key, storage_dir=str(self.root))
        path = (self.root / rel).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise UnsafeKeyError(f"Storage key escapes the storage root: {key!r}")
        return path

    def artifact_key(self, session_id: int, name: str) -> str:
        return artifact_key(session_id, name)

    # --- writes ------------------------------------------------------------

    def save_upload(self, session_id: int, filename: str, fileobj: BinaryIO) -> str:
        key = upload_key(session_id, filename)
        self.put(key, fileobj)
        return key

    def put(self, key: str, fileobj: BinaryIO, *, content_type: str | None = None) -> str:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as out:
            shutil.copyfileobj(fileobj, out)
        return key

    def put_file(self, key: str, local_path: str | Path, *, content_type: str | None = None) -> str:
        with open(local_path, "rb") as fh:
            return self.put(key, fh, content_type=content_type)

    # --- reads -------------------------------------------------------------

    def open(self, key: str, mode: str = "rb") -> BinaryIO:
        return open(self._resolve(key), mode)

    @contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        """The stored file itself — no copy, and nothing to clean up."""
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"No such stored object: {key}")
        yield path

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).exists()
        except UnsafeKeyError:
            return False

    def signed_url(self, key: str, expires_in: int | None = None) -> str | None:
        """No signing on the filesystem — the API serves these bytes directly."""
        return None

    # --- deletes -----------------------------------------------------------

    def delete(self, key: str) -> None:
        """Remove a single stored file (e.g. the source video). No-op if missing."""
        try:
            self._resolve(key).unlink(missing_ok=True)
        except UnsafeKeyError:
            return

    def delete_session(self, session_id: int) -> None:
        """Remove a session's entire storage directory (video + all artifacts)."""
        shutil.rmtree(self.root / session_prefix(session_id), ignore_errors=True)
