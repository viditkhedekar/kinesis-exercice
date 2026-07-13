"""Email-verification flow: register (unverified) → blocked login → verify → login,
plus token single-use/expiry, resend cooldown, and email validation.

Delivery uses the built-in console provider (no creds), which records messages in
``app.services.email.outbox`` so we can pull the verification link out.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import EmailVerificationToken
from app.services.email import outbox


def _client(db):
    app.dependency_overrides[get_db] = lambda: db
    outbox.clear()
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()
    outbox.clear()


def _token_from_last_email() -> str:
    assert outbox, "no verification email was sent"
    m = re.search(r"token=([A-Za-z0-9_\-]+)", outbox[-1].text)
    assert m, f"no token in email: {outbox[-1].text}"
    return m.group(1)


def _register(client, email="new@user.com", password="password123"):
    return client.post("/auth/register", json={"email": email, "name": "New", "password": password})


def test_register_is_unverified_and_sends_email(db):
    client = _client(db)
    r = _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["verification_required"] is True
    assert body["email"] == "new@user.com"
    # No session cookie on registration — the user isn't logged in yet.
    assert "kinesis_session" not in r.cookies
    assert len(outbox) == 1 and outbox[0].to == "new@user.com"


def test_login_blocked_until_verified_then_allowed(db):
    client = _client(db)
    _register(client)

    blocked = client.post("/auth/login", json={"email": "new@user.com", "password": "password123"})
    assert blocked.status_code == 403
    assert "verify" in blocked.json()["detail"].lower()

    token = _token_from_last_email()
    verified = client.post("/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert verified.json()["email_verified"] is True
    assert "kinesis_session" in verified.cookies  # logged in after verifying

    ok = client.post("/auth/login", json={"email": "new@user.com", "password": "password123"})
    assert ok.status_code == 200


def test_token_is_single_use(db):
    client = _client(db)
    _register(client)
    token = _token_from_last_email()
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    again = client.post("/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert "already been used" in again.json()["detail"]


def test_invalid_token_rejected(db):
    client = _client(db)
    r = client.post("/auth/verify-email", json={"token": "not-a-real-token"})
    assert r.status_code == 400
    assert "invalid" in r.json()["detail"].lower()


def test_expired_token_rejected(db):
    client = _client(db)
    _register(client)
    token = _token_from_last_email()
    # Age the token past expiry.
    rec = db.scalar(select(EmailVerificationToken))
    rec.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    r = client.post("/auth/verify-email", json={"token": token})
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower()


def test_resend_is_rate_limited(db):
    client = _client(db)
    _register(client)  # issues a token now
    r = client.post("/auth/resend-verification", json={"email": "new@user.com"})
    assert r.status_code == 429
    assert "wait" in r.json()["detail"].lower()


def test_resend_unknown_email_does_not_leak(db):
    client = _client(db)
    r = client.post("/auth/resend-verification", json={"email": "nobody@nowhere.com"})
    assert r.status_code == 200
    assert r.json()["sent"] is True
    assert not outbox  # nothing actually sent


def test_malformed_email_rejected_before_account_created(db):
    client = _client(db)
    for bad in ["notanemail", "no@domain", "a b@c.com", "@x.com", "x@y"]:
        r = _register(client, email=bad)
        assert r.status_code == 400, bad
        assert "valid email" in r.json()["detail"].lower()
    assert not outbox


def test_duplicate_registration_conflicts(db):
    client = _client(db)
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409
