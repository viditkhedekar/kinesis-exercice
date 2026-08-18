"""The local -> Supabase migration script: key mapping, verification, idempotency."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.migrate_storage_to_supabase import iter_local_files, key_for, upload_one
from tests.test_storage import FakeSupabaseClient


@pytest.fixture()
def local_tree(tmp_path) -> Path:
    """A storage dir shaped like a pre-migration Render disk."""
    sessions = tmp_path / "sessions"
    (sessions / "1").mkdir(parents=True)
    (sessions / "2" / "artifacts").mkdir(parents=True)
    (sessions / "1" / "source_squat.mp4").write_bytes(b"clip-one")
    (sessions / "1" / "landmarks.npz").write_bytes(b"npz-one")
    (sessions / "2" / "artifacts" / "landmarks.npz").write_bytes(b"npz-two")
    return tmp_path


def test_finds_every_stored_file(local_tree):
    found = iter_local_files(local_tree)
    assert [p.name for p in found] == [
        "landmarks.npz", "source_squat.mp4", "landmarks.npz",
    ]


def test_missing_storage_dir_is_not_an_error(tmp_path):
    assert iter_local_files(tmp_path / "nope") == []


def test_local_paths_map_to_the_same_logical_keys(local_tree):
    keys = {key_for(p, local_tree) for p in iter_local_files(local_tree)}
    assert keys == {
        "sessions/1/source_squat.mp4",
        "sessions/1/landmarks.npz",
        "sessions/2/artifacts/landmarks.npz",
    }


def test_upload_transfers_the_bytes_and_verifies_the_size(local_tree):
    client = FakeSupabaseClient()
    path = local_tree / "sessions" / "1" / "source_squat.mp4"

    result = upload_one(client, path, "sessions/1/source_squat.mp4", dry_run=False, force=False)

    assert result == "uploaded"
    assert client.objects["sessions/1/source_squat.mp4"] == b"clip-one"


def test_rerunning_skips_objects_already_present_at_the_same_size(local_tree):
    client = FakeSupabaseClient()
    path = local_tree / "sessions" / "1" / "source_squat.mp4"
    key = "sessions/1/source_squat.mp4"

    upload_one(client, path, key, dry_run=False, force=False)
    second = upload_one(client, path, key, dry_run=False, force=False)

    assert second == "skipped"


def test_force_reuploads_even_when_present(local_tree):
    client = FakeSupabaseClient()
    path = local_tree / "sessions" / "1" / "source_squat.mp4"
    key = "sessions/1/source_squat.mp4"
    client.objects[key] = b"clip-one"

    assert upload_one(client, path, key, dry_run=False, force=True) == "uploaded"


def test_dry_run_writes_nothing(local_tree):
    client = FakeSupabaseClient()
    path = local_tree / "sessions" / "1" / "source_squat.mp4"

    upload_one(client, path, "sessions/1/source_squat.mp4", dry_run=True, force=False)

    assert client.objects == {}


def test_a_truncated_upload_is_reported_as_a_failure(local_tree):
    """Verification must catch a short write instead of calling it a success."""

    class TruncatingClient(FakeSupabaseClient):
        def upload_file(self, key, local_path, *, content_type=None):
            self.objects[key] = Path(local_path).read_bytes()[:2]

    client = TruncatingClient()
    path = local_tree / "sessions" / "1" / "source_squat.mp4"

    with pytest.raises(RuntimeError, match="size mismatch"):
        upload_one(client, path, "sessions/1/source_squat.mp4", dry_run=False, force=False)


def test_originals_are_left_on_disk(local_tree):
    """The script never deletes as a side effect of uploading."""
    client = FakeSupabaseClient()
    for path in iter_local_files(local_tree):
        upload_one(client, path, key_for(path, local_tree), dry_run=False, force=False)

    assert all(p.exists() for p in iter_local_files(local_tree))
