"""Supabase Storage implementation of the ``Storage`` protocol.

The production backend. Objects live in one private bucket under the same
logical layout the filesystem backend used, so keys persisted in Postgres mean
the same thing on either side of the migration:

    sessions/<session_id>/source_<filename>
    sessions/<session_id>/artifacts/<artifact_name>

The bucket is private. Nothing is readable without either the service-role key
(backend only) or a short-lived signed URL, which the API issues *after* it has
checked that the caller owns the session.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.config import get_settings
from app.services.storage.keys import (
    artifact_key,
    normalize_reference,
    session_prefix,
    upload_key,
)
from app.services.storage.supabase_client import (
    ObjectNotFound,
    SupabaseStorageClient,
)

logger = logging.getLogger("kinesis.storage")


class SupabaseStorage:
    """Stores uploads and artifacts as objects in a Supabase Storage bucket."""

    name = "supabase"

    def __init__(
        self,
        client: SupabaseStorageClient | None = None,
        *,
        signed_url_ttl: int | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client or SupabaseStorageClient(
            settings.supabase_url or "",
            settings.supabase_service_role_key or "",
            settings.supabase_storage_bucket,
            timeout=settings.supabase_timeout,
        )
        self._ttl = signed_url_ttl or settings.supabase_signed_url_ttl
        # Legacy rows hold absolute filesystem paths; strip this prefix off them.
        self._legacy_root = str(settings.storage_dir)

    # --- key handling ------------------------------------------------------

    def _key(self, key: str) -> str:
        return normalize_reference(key, storage_dir=self._legacy_root)

    def artifact_key(self, session_id: int, name: str) -> str:
        return artifact_key(session_id, name)

    @staticmethod
    def _content_type(key: str) -> str:
        guessed, _ = mimetypes.guess_type(key)
        return guessed or "application/octet-stream"

    # --- writes ------------------------------------------------------------

    def save_upload(self, session_id: int, filename: str, fileobj: BinaryIO) -> str:
        key = upload_key(session_id, filename)
        self.put(key, fileobj)
        return key

    def put(self, key: str, fileobj: BinaryIO, *, content_type: str | None = None) -> str:
        safe = self._key(key)
        self._client.upload(safe, fileobj, content_type=content_type or self._content_type(safe))
        return safe

    def put_file(self, key: str, local_path: str | Path, *, content_type: str | None = None) -> str:
        with open(local_path, "rb") as fh:
            return self.put(key, fh, content_type=content_type)

    # --- reads -------------------------------------------------------------

    def open(self, key: str, mode: str = "rb") -> BinaryIO:
        """Fetch an object as an in-memory binary stream.

        Only used for small derived artifacts (the landmark ``.npz``), which
        ``numpy.load`` reads straight from a file-like object. Videos go through
        ``local_path`` instead so they are never held in memory.
        """
        import io

        if "w" in mode or "a" in mode:
            raise ValueError("SupabaseStorage.open is read-only; use put()")
        try:
            return io.BytesIO(self._client.download(self._key(key)))
        except ObjectNotFound as exc:
            raise FileNotFoundError(f"No such stored object: {key}") from exc

    @contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        """Download to a temp file for code that needs a real filesystem path.

        This is the bridge for the CV pipeline, which hands a path to ffmpeg /
        OpenCV. The temp file is removed in ``finally``, so it is cleaned up when
        processing raises just as when it succeeds.
        """
        safe = self._key(key)
        suffix = PurePosixPath(safe).suffix or ".bin"
        fd, tmp = tempfile.mkstemp(prefix="kinesis_", suffix=suffix)
        os.close(fd)
        try:
            try:
                self._client.download_to(safe, tmp)
            except ObjectNotFound as exc:
                raise FileNotFoundError(f"No such stored object: {key}") from exc
            yield Path(tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:  # already gone, or never created
                logger.debug("temp file cleanup skipped for %s", tmp, exc_info=True)

    def exists(self, key: str) -> bool:
        return self._client.exists(self._key(key))

    def signed_url(self, key: str, expires_in: int | None = None) -> str | None:
        """A short-lived URL for direct playback. Never persisted — it expires."""
        try:
            return self._client.create_signed_url(self._key(key), expires_in or self._ttl)
        except ObjectNotFound:
            return None

    # --- deletes -----------------------------------------------------------

    def delete(self, key: str) -> None:
        self._client.remove([self._key(key)])

    def delete_session(self, session_id: int) -> None:
        """Remove every object under the session prefix (video + all artifacts)."""
        keys = self._client.list_recursive(session_prefix(session_id))
        if keys:
            self._client.remove(keys)
