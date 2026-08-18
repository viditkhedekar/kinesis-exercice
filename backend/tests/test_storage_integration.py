"""Storage wired into the app: the CV temp-file bridge, DB keys, and playback.

Complements ``test_storage.py`` (which tests the backends in isolation) by
checking the places the rest of the app touches storage. Supabase is always the
in-memory fake — no credentials, no network.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db import get_db
from app.main import app
from app.models import AnalysisArtifact, Exercise, Session, SessionStatus, User, Video
from app.services.pose import PoseResult, load_landmarks
from app.services.storage.supabase import SupabaseStorage
from tests.test_storage import FakeSupabaseClient


@pytest.fixture()
def storage() -> SupabaseStorage:
    return SupabaseStorage(client=FakeSupabaseClient())


@pytest.fixture()
def app_storage(storage, monkeypatch):
    """Make ``get_storage()`` return the fake-backed Supabase storage app-wide."""
    import app.services.storage as storage_pkg

    monkeypatch.setattr(storage_pkg, "_storage", storage)
    yield storage
    storage_pkg.reset_storage()


def _pose(frames: int = 4) -> PoseResult:
    landmarks = np.zeros((frames, 33, 4), dtype=np.float32)
    landmarks[..., 3] = 1.0
    return PoseResult(landmarks=landmarks, fps=15.0, duration=frames / 15.0, width=640, height=480)


# --- the CV temp-file bridge ----------------------------------------------


def test_video_source_downloads_to_a_temp_file_and_removes_it(storage):
    """Supabase Storage -> temp file -> processing -> temp file deleted."""
    from app.services.pipeline import _video_source

    key = storage.save_upload(1, "clip.mp4", io.BytesIO(b"\x00\x01H264"))
    video = Video(session_id=1, path=key, filename="clip.mp4")

    with _video_source(storage, video, None) as path:
        # This is what run_pose() receives: a real, readable local file.
        assert Path(path).is_file()
        assert Path(path).read_bytes() == b"\x00\x01H264"
        temp = Path(path)
    assert not temp.exists()


def test_video_source_cleans_up_when_processing_raises(storage):
    from app.services.pipeline import _video_source

    key = storage.save_upload(1, "clip.mp4", io.BytesIO(b"data"))
    video = Video(session_id=1, path=key, filename="clip.mp4")
    seen: list[Path] = []

    with pytest.raises(RuntimeError):
        with _video_source(storage, video, None) as path:
            seen.append(Path(path))
            raise RuntimeError("pose failed")

    assert not seen[0].exists()


def test_video_source_reuses_the_uploaders_temp_file_without_downloading(storage, tmp_path):
    """The upload handler already has the clip on disk; don't round-trip it."""
    from app.services.pipeline import _video_source

    local = tmp_path / "upload.mp4"
    local.write_bytes(b"local-copy")
    video = Video(session_id=1, path="sessions/1/source_upload.mp4", filename="upload.mp4")

    with _video_source(storage, video, local) as path:
        assert Path(path) == local
    # The caller owns that file (it deletes it in its own finally) — not us.
    assert local.exists()


def test_video_source_resolves_a_legacy_absolute_path_reference(storage):
    from app.services.pipeline import _video_source

    storage._client.objects["sessions/2/source_old.mp4"] = b"legacy"
    video = Video(session_id=2, path="/data/kinesis/sessions/2/source_old.mp4", filename="old.mp4")

    with _video_source(storage, video, None) as path:
        assert Path(path).read_bytes() == b"legacy"


# --- artifacts -------------------------------------------------------------


def test_persist_landmarks_stores_a_key_and_round_trips(storage):
    from app.services.pipeline import persist_landmarks

    key = persist_landmarks(storage, 42, _pose(6))

    assert key == "sessions/42/artifacts/landmarks.npz"
    assert storage.exists(key)
    with storage.open(key) as fh:
        restored = load_landmarks(fh)
    assert restored.landmarks.shape == (6, 33, 4)
    assert restored.fps == pytest.approx(15.0)
    assert restored.width == 640


def test_landmarks_never_touch_the_local_filesystem(storage, tmp_path, monkeypatch):
    """The artifact is serialised in memory — nothing is written to disk."""
    from app.services.pipeline import persist_landmarks

    monkeypatch.chdir(tmp_path)
    persist_landmarks(storage, 42, _pose())
    assert list(tmp_path.iterdir()) == []


# --- database references ---------------------------------------------------


def _client(db):
    db.add(Exercise(key="squat", name="Squat", config_path="squat.yaml"))
    user = User(email="a@b.c", name="A", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), user


def teardown_function():
    app.dependency_overrides.clear()


def test_live_session_persists_a_storage_key_not_a_filesystem_path(db, app_storage):
    """End to end: a live workout's artifact reference is a portable key."""
    from tests.synthetic import knee_series, squat_landmarks

    client, _ = _client(db)
    session_id = client.post("/sessions/live", json={"exercise_key": "squat"}).json()["id"]

    frames = squat_landmarks(knee_series(2, bottom=85.0))
    payload = np.nan_to_num(frames, nan=0.0).tolist()
    r = client.post(
        f"/sessions/live/{session_id}/finish",
        json={
            "frames": payload,
            "timestamps": list(np.arange(len(frames)) / 30.0),
            "sets": [{"start": 0, "end": len(frames) - 1}],
        },
    )
    assert r.status_code == 200, r.text

    artifact = db.query(AnalysisArtifact).filter_by(session_id=session_id).one()
    assert artifact.landmarks_path == f"sessions/{session_id}/artifacts/landmarks.npz"
    assert not artifact.landmarks_path.startswith("/")
    assert not Path(artifact.landmarks_path).is_absolute()
    assert "/data/kinesis" not in artifact.landmarks_path
    # And the bytes really went to the bucket, not to Render's disk.
    assert app_storage.exists(artifact.landmarks_path)


def test_video_endpoint_redirects_to_a_short_lived_signed_url(db, app_storage):
    client, user = _client(db)
    session = Session(exercise_key="squat", status=SessionStatus.complete, user_id=user.id)
    db.add(session)
    db.flush()
    key = app_storage.save_upload(session.id, "clip.mp4", io.BytesIO(b"video"))
    db.add(Video(session_id=session.id, path=key, filename="clip.mp4"))
    db.commit()

    r = client.get(f"/sessions/{session.id}/video", follow_redirects=False)

    assert r.status_code == 307
    assert r.headers["location"].startswith("https://example.supabase.co/")
    assert "token=" in r.headers["location"]
    # The signed URL is minted per request and never written back to the row.
    db.refresh(session)
    assert session.video.path == key


def test_video_endpoint_404s_for_a_session_the_user_does_not_own(db, app_storage):
    client, _ = _client(db)
    other = User(email="other@b.c", name="B", password_hash="x")
    db.add(other)
    db.flush()
    session = Session(exercise_key="squat", status=SessionStatus.complete, user_id=other.id)
    db.add(session)
    db.flush()
    key = app_storage.save_upload(session.id, "clip.mp4", io.BytesIO(b"video"))
    db.add(Video(session_id=session.id, path=key, filename="clip.mp4"))
    db.commit()

    r = client.get(f"/sessions/{session.id}/video", follow_redirects=False)
    assert r.status_code == 404
    # Authorization is on the session row, so no URL is ever signed for it.
    assert app_storage._client.signed == []


def test_video_url_endpoint_returns_the_signed_url_as_json(db, app_storage):
    client, user = _client(db)
    session = Session(exercise_key="squat", status=SessionStatus.complete, user_id=user.id)
    db.add(session)
    db.flush()
    key = app_storage.save_upload(session.id, "clip.mp4", io.BytesIO(b"video"))
    db.add(Video(session_id=session.id, path=key, filename="clip.mp4"))
    db.commit()

    body = client.get(f"/sessions/{session.id}/video/url").json()
    assert body["url"].startswith("https://")
    assert body["expires_in"] > 0


def test_upload_rejects_a_disallowed_container_before_touching_storage(db, app_storage):
    """A bogus extension is a 400 — nothing is stored and no session is created."""
    client, _ = _client(db)

    r = client.post(
        "/sessions",
        data={"exercise_key": "squat"},
        files={"file": ("payload.sh", io.BytesIO(b"#!/bin/sh"), "application/x-sh")},
    )

    assert r.status_code == 400
    assert "Unsupported video type" in r.json()["detail"]
    assert app_storage._client.objects == {}
    assert db.query(Session).count() == 0
