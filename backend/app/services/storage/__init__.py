"""Storage service: persists uploaded videos and analysis artifacts.

    Storage (protocol)
    ├── FileSystemStorage   local dev / tests
    └── SupabaseStorage     production (Render -> Supabase Storage)

Application code only ever deals in **storage keys** — stable, host-independent
strings like ``sessions/12/source_squat.mp4`` — and never learns which backend is
behind them. Those keys are what Postgres stores, which is why moving from a
Render disk to a Supabase bucket needs no schema change.

Backend selection is ``KINESIS_STORAGE_BACKEND``: ``auto`` (default) picks
Supabase when it is configured and the filesystem otherwise, so local dev and the
test suite work with no Supabase account while production just sets the env vars.
"""
from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

from app.config import get_settings
from app.services.storage.filesystem import FileSystemStorage
from app.services.storage.keys import (
    ALLOWED_VIDEO_EXTENSIONS,
    UnsafeKeyError,
    artifact_key,
    normalize_reference,
    safe_filename,
    safe_key,
    session_prefix,
    upload_key,
    validate_video_filename,
)

logger = logging.getLogger("kinesis.storage")

__all__ = [
    "ALLOWED_VIDEO_EXTENSIONS",
    "FileSystemStorage",
    "Storage",
    "UnsafeKeyError",
    "artifact_key",
    "get_storage",
    "normalize_reference",
    "reset_storage",
    "safe_filename",
    "safe_key",
    "session_prefix",
    "upload_key",
    "validate_video_filename",
]


@runtime_checkable
class Storage(Protocol):
    """Everything the application needs from a storage backend.

    All methods take/return keys, never filesystem paths. Implementations accept
    legacy absolute paths for keys too, so rows written before the Supabase
    migration keep resolving.
    """

    def save_upload(self, session_id: int, filename: str, fileobj: BinaryIO) -> str:
        """Store an uploaded clip; returns its key."""

    def artifact_key(self, session_id: int, name: str) -> str:
        """The key a named analysis artifact for this session should live at."""

    def put(self, key: str, fileobj: BinaryIO, *, content_type: str | None = None) -> str:
        """Write a file-like object at ``key``; returns the (normalised) key."""

    def put_file(self, key: str, local_path: str | Path, *, content_type: str | None = None) -> str:
        """Write a local file at ``key``; returns the (normalised) key."""

    def open(self, key: str, mode: str = "rb") -> BinaryIO:
        """Open a stored object for reading."""

    def local_path(self, key: str) -> AbstractContextManager[Path]:
        """Context manager yielding a real filesystem path for the object.

        The bridge for code that cannot take a stream — the CV pipeline hands a
        path to ffmpeg/OpenCV. Remote backends download to a temp file and delete
        it on exit, including when the body raises.
        """

    def exists(self, key: str) -> bool:
        """Whether an object is stored at ``key``."""

    def signed_url(self, key: str, expires_in: int | None = None) -> str | None:
        """A time-limited direct URL, or ``None`` when the backend can't sign."""

    def delete(self, key: str) -> None:
        """Delete one object. Missing objects are a no-op."""

    def delete_session(self, session_id: int) -> None:
        """Delete every object belonging to a session."""


# One instance per process: the Supabase backend holds a pooled HTTP client, and
# rebuilding it per request would throw away connection reuse.
_storage: Storage | None = None


def _build_storage() -> Storage:
    settings = get_settings()
    backend = settings.resolve_storage_backend()
    if backend == "supabase":
        from app.services.storage.supabase import SupabaseStorage

        logger.info(
            "storage backend: supabase (bucket=%s)", settings.supabase_storage_bucket
        )
        return SupabaseStorage()
    if backend != "filesystem":
        raise ValueError(
            f"Unknown KINESIS_STORAGE_BACKEND={settings.storage_backend!r} "
            "(expected 'auto', 'supabase', or 'filesystem')"
        )
    logger.info("storage backend: filesystem (dir=%s)", settings.storage_dir)
    return FileSystemStorage()


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = _build_storage()
    return _storage


def reset_storage() -> None:
    """Drop the cached backend (tests, and after changing settings at runtime)."""
    global _storage
    _storage = None
