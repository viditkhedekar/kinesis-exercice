"""Storage abstraction: keys, both backends, and the temp-file bridge.

No real Supabase credentials are used anywhere here — the REST client is either
swapped for an in-memory fake or driven through an ``httpx.MockTransport``.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest

from app.services.storage import FileSystemStorage, Storage
from app.services.storage.keys import (
    UnsafeKeyError,
    artifact_key,
    normalize_reference,
    safe_filename,
    safe_key,
    upload_key,
    validate_video_filename,
)
from app.services.storage.supabase import SupabaseStorage
from app.services.storage.supabase_client import (
    ObjectNotFound,
    SupabaseStorageClient,
)


# --- fakes -----------------------------------------------------------------


class FakeSupabaseClient:
    """In-memory stand-in for ``SupabaseStorageClient``."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.signed: list[tuple[str, int]] = []

    def upload(self, key, fileobj, *, content_type=None):
        self.objects[key] = fileobj.read()

    def upload_file(self, key, local_path, *, content_type=None):
        self.objects[key] = Path(local_path).read_bytes()

    def download(self, key):
        if key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]

    def download_to(self, key, dest):
        Path(dest).write_bytes(self.download(key))

    def exists(self, key):
        return key in self.objects

    def size(self, key):
        return len(self.objects[key]) if key in self.objects else None

    def remove(self, keys):
        for k in keys:
            self.objects.pop(k, None)

    def list_recursive(self, prefix):
        base = prefix.rstrip("/") + "/"
        return [k for k in self.objects if k.startswith(base)]

    def create_signed_url(self, key, expires_in):
        if key not in self.objects:
            raise ObjectNotFound(key)
        self.signed.append((key, expires_in))
        return f"https://example.supabase.co/storage/v1/object/sign/{key}?token=abc"


@pytest.fixture()
def fs_storage(tmp_path) -> FileSystemStorage:
    return FileSystemStorage(root=tmp_path)


@pytest.fixture()
def supabase_storage() -> SupabaseStorage:
    return SupabaseStorage(client=FakeSupabaseClient())


@pytest.fixture(params=["filesystem", "supabase"])
def storage(request, tmp_path):
    """Both backends, so the shared contract is asserted against each."""
    if request.param == "filesystem":
        return FileSystemStorage(root=tmp_path)
    return SupabaseStorage(client=FakeSupabaseClient())


# --- keys ------------------------------------------------------------------


def test_keys_use_the_documented_logical_layout():
    assert upload_key(12, "squat.mp4") == "sessions/12/source_squat.mp4"
    assert artifact_key(12, "landmarks.npz") == "sessions/12/artifacts/landmarks.npz"


@pytest.mark.parametrize(
    "hostile",
    [
        "../../../etc/passwd",
        "..%2f..%2fetc%2fpasswd",
        "/etc/passwd",
        "....//....//etc/passwd",
        r"C:\Windows\system32\evil.mp4",
        "sub/dir/evil.mp4",
        "..",
        ".",
        "",
    ],
)
def test_safe_filename_never_escapes_its_component(hostile):
    safe = safe_filename(hostile)
    assert "/" not in safe and "\\" not in safe
    assert safe not in {"", ".", ".."}
    assert not safe.startswith(".")


def test_upload_key_stays_inside_the_session_prefix_for_traversal_attempts():
    key = upload_key(7, "../../../../etc/passwd")
    assert key.startswith("sessions/7/source_")
    assert ".." not in key


def test_validate_video_filename_rejects_disallowed_extensions():
    assert validate_video_filename("Squat Clip.MP4") == "Squat_Clip.MP4"
    with pytest.raises(UnsafeKeyError):
        validate_video_filename("payload.sh")
    with pytest.raises(UnsafeKeyError):
        validate_video_filename("no_extension")


@pytest.mark.parametrize(
    "bad", ["../secrets", "sessions/../../etc", "sessions//12/x", "a\\b", "", "   "]
)
def test_safe_key_rejects_traversal(bad):
    with pytest.raises(UnsafeKeyError):
        safe_key(bad)


def test_normalize_reference_converts_legacy_absolute_paths():
    # Rows written before the migration hold absolute paths; they must resolve.
    assert (
        normalize_reference("/data/kinesis/sessions/3/landmarks.npz", storage_dir="/data/kinesis")
        == "sessions/3/landmarks.npz"
    )
    # Even when storage_dir no longer matches the path the row was written with.
    assert (
        normalize_reference("/mnt/old/sessions/3/source_a.mp4", storage_dir="/data/kinesis")
        == "sessions/3/source_a.mp4"
    )
    # Already a key: unchanged (so the migration is idempotent).
    assert normalize_reference("sessions/3/artifacts/landmarks.npz") == (
        "sessions/3/artifacts/landmarks.npz"
    )


# --- shared backend contract ----------------------------------------------


def test_both_backends_satisfy_the_storage_protocol(storage):
    assert isinstance(storage, Storage)


def test_save_upload_returns_a_key_not_a_local_path(storage):
    key = storage.save_upload(5, "my clip.mp4", io.BytesIO(b"video-bytes"))
    assert key == "sessions/5/source_my_clip.mp4"
    assert not key.startswith("/")
    assert not Path(key).is_absolute()


def test_upload_then_download_roundtrip(storage):
    key = storage.save_upload(1, "a.mp4", io.BytesIO(b"payload"))
    with storage.open(key) as fh:
        assert fh.read() == b"payload"


def test_exists_and_delete(storage):
    key = storage.save_upload(2, "a.mp4", io.BytesIO(b"x"))
    assert storage.exists(key)
    storage.delete(key)
    assert not storage.exists(key)


def test_delete_is_a_noop_for_missing_objects(storage):
    storage.delete("sessions/999/source_missing.mp4")  # must not raise


def test_open_missing_object_raises_filenotfound(storage):
    with pytest.raises(FileNotFoundError):
        storage.open("sessions/404/artifacts/landmarks.npz")


def test_local_path_missing_object_raises_filenotfound(storage):
    with pytest.raises(FileNotFoundError):
        with storage.local_path("sessions/404/source_x.mp4"):
            pass


def test_delete_session_removes_video_and_artifacts(storage):
    video = storage.save_upload(9, "a.mp4", io.BytesIO(b"v"))
    art = storage.artifact_key(9, "landmarks.npz")
    storage.put(art, io.BytesIO(b"l"))
    other = storage.save_upload(10, "b.mp4", io.BytesIO(b"keep"))

    storage.delete_session(9)

    assert not storage.exists(video)
    assert not storage.exists(art)
    assert storage.exists(other)  # a neighbouring session is untouched


def test_traversal_key_is_rejected_by_the_backends(storage):
    with pytest.raises(UnsafeKeyError):
        storage.put("../../escape.txt", io.BytesIO(b"x"))


# --- filesystem specifics --------------------------------------------------


def test_filesystem_writes_under_the_documented_layout(fs_storage, tmp_path):
    fs_storage.save_upload(4, "clip.mp4", io.BytesIO(b"v"))
    assert (tmp_path / "sessions" / "4" / "source_clip.mp4").is_file()


def test_filesystem_local_path_is_the_stored_file_and_survives(fs_storage):
    key = fs_storage.save_upload(4, "clip.mp4", io.BytesIO(b"v"))
    with fs_storage.local_path(key) as path:
        assert path.read_bytes() == b"v"
        kept = path
    assert kept.exists()  # nothing to clean up: it IS the stored object


def test_filesystem_reads_legacy_absolute_paths(fs_storage, tmp_path):
    """A pre-migration DB row still resolves against the same root."""
    fs_storage.save_upload(6, "clip.mp4", io.BytesIO(b"legacy"))
    legacy = str(tmp_path / "sessions" / "6" / "source_clip.mp4")
    with fs_storage.open(legacy) as fh:
        assert fh.read() == b"legacy"


def test_filesystem_cannot_be_signed(fs_storage):
    key = fs_storage.save_upload(4, "clip.mp4", io.BytesIO(b"v"))
    assert fs_storage.signed_url(key) is None


# --- supabase specifics ----------------------------------------------------


def test_supabase_signed_url_is_minted_per_request(supabase_storage):
    key = supabase_storage.save_upload(3, "clip.mp4", io.BytesIO(b"v"))
    url = supabase_storage.signed_url(key, expires_in=60)
    assert url.startswith("https://") and "token=" in url
    assert supabase_storage._client.signed == [(key, 60)]


def test_supabase_signed_url_for_missing_object_is_none(supabase_storage):
    assert supabase_storage.signed_url("sessions/1/source_gone.mp4") is None


def test_supabase_local_path_downloads_then_deletes_the_temp_file(supabase_storage):
    key = supabase_storage.save_upload(8, "clip.mp4", io.BytesIO(b"frames"))
    with supabase_storage.local_path(key) as path:
        assert path.exists() and path.read_bytes() == b"frames"
        assert path.suffix == ".mp4"  # ffmpeg sniffs the container from the name
        temp = path
    assert not temp.exists()


def test_supabase_temp_file_is_cleaned_up_when_processing_fails(supabase_storage):
    """The CV pipeline raising must not leak the downloaded clip on Render's disk."""
    key = supabase_storage.save_upload(8, "clip.mp4", io.BytesIO(b"frames"))
    leaked: list[Path] = []
    with pytest.raises(RuntimeError):
        with supabase_storage.local_path(key) as path:
            leaked.append(path)
            raise RuntimeError("pose estimation blew up")
    assert not leaked[0].exists()


def test_supabase_resolves_legacy_absolute_path_references(supabase_storage):
    supabase_storage._client.objects["sessions/11/landmarks.npz"] = b"old"
    with supabase_storage.open("/data/kinesis/sessions/11/landmarks.npz") as fh:
        assert fh.read() == b"old"


# --- the REST client itself (mocked transport, no credentials) -------------


def _client(handler) -> SupabaseStorageClient:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(
        base_url="https://proj.supabase.co/storage/v1",
        transport=transport,
        headers={"Authorization": "Bearer test-key"},
    )
    return SupabaseStorageClient(
        "https://proj.supabase.co", "test-key", "media", client=http
    )


def test_client_uploads_to_the_bucket_scoped_object_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["upsert"] = request.headers.get("x-upsert")
        seen["body"] = request.content
        return httpx.Response(200, json={"Key": "media/sessions/1/source_a.mp4"})

    _client(handler).upload("sessions/1/source_a.mp4", io.BytesIO(b"bytes"))
    assert seen["url"].endswith("/object/media/sessions/1/source_a.mp4")
    assert seen["upsert"] == "true"
    assert seen["body"] == b"bytes"


def test_client_download_maps_404_to_object_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not_found"})

    with pytest.raises(ObjectNotFound):
        _client(handler).download("sessions/1/nope.mp4")


def test_client_exists_is_false_on_404_and_true_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200 if "here" in str(request.url) else 404)

    client = _client(handler)
    assert client.exists("sessions/1/here.mp4") is True
    assert client.exists("sessions/1/gone.mp4") is False


def test_client_builds_an_absolute_signed_url_from_the_relative_one():
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["expiresIn"] == 900
        return httpx.Response(
            200, json={"signedURL": "/object/sign/media/sessions/1/a.mp4?token=xyz"}
        )

    url = _client(handler).create_signed_url("sessions/1/a.mp4", 900)
    assert url == (
        "https://proj.supabase.co/storage/v1/object/sign/media/sessions/1/a.mp4?token=xyz"
    )


def test_client_requires_credentials():
    with pytest.raises(Exception):
        SupabaseStorageClient("", "", "media")


def test_client_percent_encodes_keys_but_keeps_the_path_separators():
    """Key segments are escaped for the URL; the ``/`` structure is preserved."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["raw"] = request.url.raw_path.decode()
        return httpx.Response(200, json={})

    _client(handler).upload("sessions/1/source_a b.mp4", io.BytesIO(b""))
    assert seen["raw"] == "/storage/v1/object/media/sessions/1/source_a%20b.mp4"
