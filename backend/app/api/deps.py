"""Shared API dependencies — current-user resolution from the session cookie."""
from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.services.auth import decode_token


def get_current_user(
    db: DbSession = Depends(get_db),
    kinesis_session: str | None = Cookie(default=None),
) -> User:
    """Resolve the authenticated user or raise 401. Cookie name is fixed by the
    parameter name; it matches ``settings.auth_cookie``."""
    if not kinesis_session:
        raise HTTPException(401, "Not authenticated")
    user_id = decode_token(kinesis_session)
    if user_id is None:
        raise HTTPException(401, "Invalid or expired session")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "User not found")
    return user


# The cookie parameter must literally be named after the configured cookie.
assert get_settings().auth_cookie == "kinesis_session", "cookie name must match the dependency param"
