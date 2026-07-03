"""Live Camera Mode API: create → score → finish → report, end to end.

Uses the in-memory SQLite ``db`` fixture with FastAPI dependency overrides for
auth and the DB session. Landmarks are synthetic squat frames (no MediaPipe).
"""
from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db import get_db
from app.main import app
from app.models import Exercise, User
from tests.synthetic import knee_series, squat_landmarks


def _client(db):
    """A TestClient whose DB + auth resolve to the fixture session and a user."""
    db.add(Exercise(key="squat", name="Squat", config_path="squat.yaml"))
    user = User(email="a@b.c", name="A", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)  # no `with` → skip lifespan (which needs Postgres seed)
    return client, user


def _frames(landmarks: np.ndarray) -> list:
    """(F,33,4) → JSON-able nested lists, NaN → 0 (matches the browser payload)."""
    return np.nan_to_num(landmarks, nan=0.0).tolist()


def teardown_function():
    app.dependency_overrides.clear()


def test_create_score_finish_flow(db):
    client, _ = _client(db)

    # 1. Create a live session.
    r = client.post("/sessions/live", json={"exercise_key": "squat"})
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]
    assert r.json()["mode"] == "live"

    # 2. Score the current set mid-workout (shallow squats → a depth cue).
    shallow = squat_landmarks(knee_series(2, bottom=120.0))
    r = client.post(
        f"/sessions/live/{session_id}/score",
        json={"fps": 15.0, "frames": _frames(shallow)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rep_count"] == 2
    assert body["latest_cue"] is not None
    assert body["latest_cue"]["tip"]  # a coaching tip is surfaced

    # 3. Finish: two sets with a rest gap.
    set_a = squat_landmarks(knee_series(2, bottom=85.0))
    rest = squat_landmarks([165.0] * 15)
    set_b = squat_landmarks(knee_series(3, bottom=85.0))
    full = np.concatenate([set_a, rest, set_b])
    a_end = len(set_a) - 1
    b_start = len(set_a) + len(rest)
    ts = list(np.arange(len(full)) / 30.0)  # captured at ~30 fps

    r = client.post(
        f"/sessions/live/{session_id}/finish",
        json={
            "frames": _frames(full),
            "timestamps": ts,
            "sets": [{"start": 0, "end": a_end}, {"start": b_start, "end": len(full) - 1}],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["session_id"] == session_id

    # 4. The report reflects a completed live workout with set + TUT extras.
    r = client.get(f"/sessions/{session_id}/report")
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["session"]["status"] == "complete"
    assert report["session"]["mode"] == "live"
    assert len(report["reps"]) == 5
    assert len(report["sets"]) == 2
    assert {s["set_index"] for s in report["sets"]} == {1, 2}
    assert report["sets"][0]["rep_count"] == 2 and report["sets"][1]["rep_count"] == 3
    assert report["time_under_tension"] is not None and report["time_under_tension"] > 0
    assert report["duration_s"] is not None


def test_score_with_too_few_frames_returns_empty(db):
    client, _ = _client(db)
    session_id = client.post("/sessions/live", json={"exercise_key": "squat"}).json()["id"]
    r = client.post(f"/sessions/live/{session_id}/score", json={"fps": 15.0, "frames": []})
    assert r.status_code == 200
    assert r.json() == {"reps": [], "rep_count": 0, "running_score": 0.0, "latest_cue": None}


def test_unknown_exercise_rejected(db):
    client, _ = _client(db)
    r = client.post("/sessions/live", json={"exercise_key": "nope"})
    assert r.status_code == 400
