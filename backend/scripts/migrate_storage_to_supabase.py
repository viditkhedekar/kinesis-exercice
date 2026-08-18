"""Copy locally-stored videos/artifacts into Supabase Storage.

One-shot (but re-runnable) migration for installs that predate the Supabase
backend and still have files under ``KINESIS_STORAGE_DIR`` — typically a Render
persistent disk mounted at ``/data/kinesis``.

What it does, per file found under ``<storage_dir>/sessions/``:

  1. derives the storage key from the path (``sessions/12/landmarks.npz``), so
     the logical layout is preserved exactly;
  2. uploads it, skipping objects that already exist at the same size (this is
     what makes re-runs cheap and safe);
  3. verifies the upload by reading the stored object's size back;
  4. rewrites the matching database references from absolute paths to keys.

It NEVER deletes a local file unless you pass ``--delete-local``, and even then
only after every upload has verified.

Usage (from ``backend/``):

    python -m scripts.migrate_storage_to_supabase --dry-run
    python -m scripts.migrate_storage_to_supabase
    python -m scripts.migrate_storage_to_supabase --no-update-db
    python -m scripts.migrate_storage_to_supabase --delete-local   # explicit opt-in

Requires SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_STORAGE_BUCKET and
KINESIS_DATABASE_URL in the environment.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.services.storage.keys import normalize_reference  # noqa: E402
from app.services.storage.supabase_client import SupabaseStorageClient  # noqa: E402


@dataclass
class Stats:
    uploaded: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    db_updated: int = 0
    deleted: int = 0


def iter_local_files(storage_dir: Path) -> list[Path]:
    """Every regular file under ``<storage_dir>/sessions/``, sorted for stable runs."""
    root = storage_dir / "sessions"
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def key_for(path: Path, storage_dir: Path) -> str:
    """Local path -> the same logical object key ('sessions/12/landmarks.npz')."""
    return normalize_reference(str(path), storage_dir=str(storage_dir))


def upload_one(
    client: SupabaseStorageClient, path: Path, key: str, *, dry_run: bool, force: bool
) -> str:
    """Upload one file and verify it. Returns 'uploaded', 'skipped' or raises."""
    local_size = path.stat().st_size
    if not force:
        remote_size = client.size(key)
        if remote_size is not None and remote_size == local_size:
            return "skipped"
    if dry_run:
        return "uploaded"
    client.upload_file(key, path)
    # Verify: the object must now exist, and match the local size when the API
    # reports one. A short/truncated upload must never be treated as success.
    verified = client.size(key)
    if verified is None:
        if not client.exists(key):
            raise RuntimeError(f"upload not visible after write: {key}")
    elif verified != local_size:
        raise RuntimeError(
            f"size mismatch after upload for {key}: local={local_size} remote={verified}"
        )
    return "uploaded"


def update_db_references(storage_dir: Path, *, dry_run: bool) -> int:
    """Rewrite absolute-path file references in Postgres to storage keys.

    Idempotent: a row already holding a key normalises to itself and is skipped.
    """
    from app.db import SessionLocal
    from app.models import AnalysisArtifact, Video

    changed = 0
    db = SessionLocal()
    try:
        for video in db.query(Video).all():
            key = normalize_reference(video.path, storage_dir=str(storage_dir))
            if key != video.path:
                print(f"  db videos.id={video.id}: {video.path} -> {key}")
                video.path = key
                changed += 1
        for art in db.query(AnalysisArtifact).all():
            key = normalize_reference(art.landmarks_path, storage_dir=str(storage_dir))
            if key != art.landmarks_path:
                print(f"  db analysis_artifacts.id={art.id}: {art.landmarks_path} -> {key}")
                art.landmarks_path = key
                changed += 1
            if art.metrics_path:
                mkey = normalize_reference(art.metrics_path, storage_dir=str(storage_dir))
                if mkey != art.metrics_path:
                    art.metrics_path = mkey
                    changed += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    parser.add_argument(
        "--force", action="store_true", help="re-upload even when the object already matches"
    )
    parser.add_argument(
        "--no-update-db", action="store_true", help="skip rewriting database references"
    )
    parser.add_argument(
        "--delete-local",
        action="store_true",
        help="delete each local file AFTER every upload verified (off by default)",
    )
    parser.add_argument("--storage-dir", help="override KINESIS_STORAGE_DIR")
    args = parser.parse_args(argv)

    settings = get_settings()
    storage_dir = Path(args.storage_dir or settings.storage_dir)
    if not settings.supabase_configured():
        print(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set — nothing to migrate to.",
            file=sys.stderr,
        )
        return 2

    client = SupabaseStorageClient(
        settings.supabase_url or "",
        settings.supabase_service_role_key or "",
        settings.supabase_storage_bucket,
        timeout=settings.supabase_timeout,
    )
    if not args.dry_run and client.ensure_bucket(public=False):
        print(f"created private bucket '{settings.supabase_storage_bucket}'")

    files = iter_local_files(storage_dir)
    print(
        f"{'DRY RUN: ' if args.dry_run else ''}migrating {len(files)} file(s) from "
        f"{storage_dir} to bucket '{settings.supabase_storage_bucket}'"
    )

    stats = Stats()
    migrated: list[Path] = []
    for path in files:
        key = key_for(path, storage_dir)
        try:
            result = upload_one(client, path, key, dry_run=args.dry_run, force=args.force)
        except Exception as exc:  # noqa: BLE001 — one bad file must not stop the run
            stats.failed.append(f"{key}: {exc}")
            print(f"  FAILED  {key}: {exc}", file=sys.stderr)
            continue
        if result == "skipped":
            stats.skipped += 1
            print(f"  skipped {key} (already present, same size)")
        else:
            stats.uploaded += 1
            migrated.append(path)
            print(f"  uploaded {key} ({path.stat().st_size} bytes)")

    if not args.no_update_db:
        print("updating database references...")
        stats.db_updated = update_db_references(storage_dir, dry_run=args.dry_run)

    # Deletion is opt-in and only ever runs when nothing failed.
    if args.delete_local and not args.dry_run:
        if stats.failed:
            print("refusing to delete local files: some uploads failed", file=sys.stderr)
        else:
            for path in migrated:
                path.unlink(missing_ok=True)
                stats.deleted += 1

    print(
        f"\ndone: {stats.uploaded} uploaded, {stats.skipped} skipped, "
        f"{len(stats.failed)} failed, {stats.db_updated} db reference(s) updated, "
        f"{stats.deleted} local file(s) deleted"
    )
    if stats.failed:
        print("\nfailures:", file=sys.stderr)
        for line in stats.failed:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
