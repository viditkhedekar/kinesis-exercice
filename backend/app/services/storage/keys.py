"""Object-key construction and validation.

Storage keys are the *stable* identifiers persisted in Postgres. They are host
independent (``sessions/123/source_squat.mp4``, never
``/data/kinesis/sessions/123/source_squat.mp4``) so the database survives a move
between the local filesystem, Supabase, or anything else.

Everything user-controlled — upload filenames above all — funnels through
``safe_filename``/``safe_key`` here. A key is only ever built from an integer
session id plus a sanitised single path component, so a filename can never climb
out of its session prefix or escape the bucket.
"""
from __future__ import annotations

import posixpath
import re
from pathlib import PurePosixPath

# Container/extension allowlist for uploads. Anything else is rejected at the API
# boundary rather than sanitised into something that looks valid.
ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".qt", ".webm", ".mkv", ".avi", ".mpeg", ".mpg", ".3gp",
}

# Characters allowed in a stored filename. Supabase keys are URL paths, and this
# also keeps the filesystem backend boring on every OS.
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_REPEAT_UNDERSCORE = re.compile(r"_{2,}")

_MAX_NAME_LEN = 128


class UnsafeKeyError(ValueError):
    """A filename or key that we refuse to turn into a storage key."""


def safe_filename(name: str, default: str = "video.mp4") -> str:
    """Reduce arbitrary client input to one safe path component.

    Takes only the basename (so ``../../etc/passwd`` and ``C:\\evil\\x.mp4``
    collapse to ``passwd``/``x.mp4``), replaces anything outside
    ``[A-Za-z0-9._-]``, and refuses the traversal-flavoured leftovers (``.``,
    ``..``, empty). Never returns a value containing ``/``, ``\\`` or a leading dot.
    """
    raw = (name or "").replace("\\", "/").strip()
    base = PurePosixPath(raw).name
    cleaned = _UNSAFE_CHARS.sub("_", base)
    cleaned = _REPEAT_UNDERSCORE.sub("_", cleaned).strip("._")
    if not cleaned or cleaned in {".", ".."}:
        cleaned = _UNSAFE_CHARS.sub("_", default).strip("._")
    if len(cleaned) > _MAX_NAME_LEN:
        stem, dot, ext = cleaned.rpartition(".")
        if dot and len(ext) <= 8:
            cleaned = stem[: _MAX_NAME_LEN - len(ext) - 1] + "." + ext
        else:
            cleaned = cleaned[:_MAX_NAME_LEN]
    return cleaned


def validate_video_filename(name: str) -> str:
    """Sanitise an uploaded video filename and enforce the extension allowlist.

    Raises ``UnsafeKeyError`` for an unsupported container so the caller can
    return a 400 instead of storing something the CV pipeline can't decode.
    """
    safe = safe_filename(name, default="video.mp4")
    ext = PurePosixPath(safe).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
        raise UnsafeKeyError(
            f"Unsupported video type '{ext or safe}'. Supported formats: {allowed}."
        )
    return safe


def session_prefix(session_id: int) -> str:
    """``sessions/<id>`` — the root of everything belonging to one session."""
    return f"sessions/{int(session_id)}"


def upload_key(session_id: int, filename: str) -> str:
    """``sessions/<id>/source_<filename>`` — the raw uploaded clip."""
    return f"{session_prefix(session_id)}/source_{safe_filename(filename)}"


def artifact_key(session_id: int, name: str) -> str:
    """``sessions/<id>/artifacts/<name>`` — a derived analysis artifact."""
    return f"{session_prefix(session_id)}/artifacts/{safe_filename(name, default='artifact.bin')}"


def safe_key(key: str) -> str:
    """Validate an already-built key. Raises ``UnsafeKeyError`` if it could escape.

    Rejects absolute keys, empty/``.``/``..`` segments, and backslashes — the
    shapes that would let a stored reference reach outside its bucket prefix or,
    on the filesystem backend, outside ``storage_dir``.
    """
    if not key or not key.strip():
        raise UnsafeKeyError("Empty storage key")
    if "\\" in key:
        raise UnsafeKeyError(f"Invalid storage key: {key!r}")
    normalized = key.strip().lstrip("/")
    segments = normalized.split("/")
    if any(seg in {"", ".", ".."} for seg in segments):
        raise UnsafeKeyError(f"Invalid storage key: {key!r}")
    # Belt and braces: normpath must not change anything or climb out.
    if posixpath.normpath(normalized) != normalized:
        raise UnsafeKeyError(f"Invalid storage key: {key!r}")
    return normalized


def normalize_reference(ref: str, storage_dir: str | None = None) -> str:
    """Coerce a persisted file reference into a storage key.

    New rows store keys directly. Rows written before the Supabase migration hold
    absolute filesystem paths (``/data/kinesis/sessions/12/landmarks.npz``); those
    are trimmed back to the ``sessions/...`` key so old sessions keep resolving
    against either backend without a data migration.
    """
    if ref is None:
        raise UnsafeKeyError("Empty storage key")
    candidate = str(ref).replace("\\", "/").strip()
    if storage_dir:
        root = str(storage_dir).replace("\\", "/").rstrip("/")
        if root and candidate.startswith(root + "/"):
            candidate = candidate[len(root) + 1:]
    if candidate.startswith("/"):
        # Any other absolute path: keep everything from the last "sessions/" marker.
        marker = candidate.rfind("/sessions/")
        if marker != -1:
            candidate = candidate[marker + 1:]
    return safe_key(candidate)
