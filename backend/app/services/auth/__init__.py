"""Authentication primitives: password hashing and signed session tokens.

Stdlib-only (no bcrypt / PyJWT dependency):
- Passwords: PBKDF2-HMAC-SHA256 with a per-password salt, stored as
  ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``.
- Session tokens: a compact HMAC-SHA256-signed token (``payload.signature``,
  base64url) carrying the user id and an expiry. Tamper-evident and stateless.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from app.config import get_settings

_ITERATIONS = 200_000


# --------------------- single-use verification tokens --------------------- #
# Unlike the stateless HMAC session/reset tokens above, verification tokens are
# random secrets tracked in the DB by their hash, so they can be single-use and
# revocable. Only ``hash_token(raw)`` is ever stored; the raw value lives only in
# the emailed link.

def new_verification_token() -> str:
    """A high-entropy, URL-safe token for email verification links."""
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    """SHA-256 hex digest — what we persist and look up by."""
    return hashlib.sha256(raw.encode()).hexdigest()


# --------------------------- passwords --------------------------- #

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


# --------------------------- tokens --------------------------- #

def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload_b64: str) -> str:
    secret = get_settings().auth_secret.encode()
    sig = hmac.new(secret, payload_b64.encode(), hashlib.sha256).digest()
    return _b64e(sig)


def create_token(user_id: int, ttl_seconds: int, purpose: str = "session") -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + ttl_seconds, "purpose": purpose}
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def decode_token(token: str, purpose: str = "session") -> int | None:
    """Return the user id if the token is valid, unexpired, and signed by us."""
    try:
        payload_b64, sig = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(payload_b64)):
        return None
    try:
        payload = json.loads(_b64d(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("purpose") != purpose or payload.get("exp", 0) < time.time():
        return None
    return int(payload["sub"])
