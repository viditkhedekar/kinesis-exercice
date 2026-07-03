from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas import ForgotIn, LoginIn, PrefsIn, RegisterIn, ResetIn, UserOut
from app.services.auth import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

DEFAULT_PREFS = {"onboarded": False, "goals": [], "exercises": []}


def _set_session_cookie(response: Response, user_id: int, remember: bool) -> None:
    days = settings.remember_days if remember else settings.session_days
    token = create_token(user_id, ttl_seconds=days * 86400)
    response.set_cookie(
        key=settings.auth_cookie,
        value=token,
        max_age=days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.auth_cookie_secure,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, response: Response, db: DbSession = Depends(get_db)) -> UserOut:
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "A valid email is required")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(
        email=email,
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        prefs=dict(DEFAULT_PREFS),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user.id, remember=True)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: DbSession = Depends(get_db)) -> UserOut:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    _set_session_cookie(response, user.id, remember=body.remember)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(settings.auth_cookie, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: PrefsIn, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)
) -> UserOut:
    if body.name is not None:
        user.name = body.name.strip()
    if body.prefs is not None:
        user.prefs = {**(user.prefs or DEFAULT_PREFS), **body.prefs}
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/forgot")
def forgot(body: ForgotIn, db: DbSession = Depends(get_db)) -> dict:
    """Issue a password-reset token. No email is sent in this build — the token
    is returned directly so the reset flow is exercisable end-to-end."""
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None:
        # Don't reveal whether the email exists.
        return {"sent": True, "token": None}
    token = create_token(user.id, ttl_seconds=3600, purpose="reset")
    return {"sent": True, "token": token}


@router.post("/reset", response_model=UserOut)
def reset(body: ResetIn, response: Response, db: DbSession = Depends(get_db)) -> UserOut:
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    user_id = decode_token(body.token, purpose="reset")
    if user_id is None:
        raise HTTPException(400, "Invalid or expired reset link")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(400, "Invalid reset link")
    user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user.id, remember=False)
    return UserOut.model_validate(user)
