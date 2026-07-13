from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas import (
    ForgotIn,
    LoginIn,
    PrefsIn,
    RegisterIn,
    RegisterOut,
    ResendOut,
    ResendVerificationIn,
    ResetIn,
    UserOut,
    VerifyEmailIn,
)
from app.services.auth import create_token, decode_token, hash_password, verify_password
from app.services.email import EmailError
from app.services.verification import (
    consume_token,
    is_valid_email,
    issue_token,
    seconds_until_resend_allowed,
    send_verification_email,
)

logger = logging.getLogger("kinesis.auth")

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

DEFAULT_PREFS = {"onboarded": False, "goals": [], "exercises": []}

# Verification codes the frontend keys off (kept human-readable in the message too).
_VERIFY_MESSAGES = {
    "invalid": "This verification link is invalid. Request a new one below.",
    "used": "This verification link has already been used. Try logging in, or request a new link.",
    "expired": "This verification link has expired. Request a new one below.",
}


def _cookie_samesite_secure() -> tuple[str, bool]:
    """Resolve the SameSite/Secure pair for the session cookie.

    Browsers reject a ``SameSite=None`` cookie unless it is also ``Secure``, so
    force Secure on whenever SameSite is None — otherwise the cross-site cookie
    would be silently dropped by the browser and never stored.
    """
    samesite = settings.auth_cookie_samesite.lower()
    secure = settings.auth_cookie_secure or samesite == "none"
    return samesite, secure


def _set_session_cookie(response: Response, user_id: int, remember: bool) -> None:
    days = settings.remember_days if remember else settings.session_days
    token = create_token(user_id, ttl_seconds=days * 86400)
    samesite, secure = _cookie_samesite_secure()
    response.set_cookie(
        key=settings.auth_cookie,
        value=token,
        max_age=days * 86400,
        httponly=True,
        samesite=samesite,
        secure=secure,
        path="/",
    )


def _dispatch_verification(db: DbSession, user: User) -> None:
    """Issue a token and send the verification email. Never fails the request on a
    delivery error — the account exists and the user can resend from the UI."""
    raw = issue_token(db, user)
    db.commit()
    try:
        send_verification_email(user, raw)
    except EmailError as exc:  # provider down / misconfigured
        logger.error("Verification email to %s failed: %s", user.email, exc)


@router.post("/register", response_model=RegisterOut, status_code=201)
def register(body: RegisterIn, db: DbSession = Depends(get_db)) -> RegisterOut:
    email = body.email.strip().lower()
    if not is_valid_email(email):
        raise HTTPException(400, "Please enter a valid email address.")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")

    user = User(
        email=email,
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        email_verified=False,
        prefs=dict(DEFAULT_PREFS),
    )
    db.add(user)
    db.flush()
    _dispatch_verification(db, user)

    return RegisterOut(
        email=email,
        verification_required=True,
        message="Account created. Check your inbox to confirm your email address.",
    )


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: DbSession = Depends(get_db)) -> UserOut:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if settings.require_email_verification and not user.email_verified:
        # 403 (not 401) so the client can distinguish "verify your email" from
        # "wrong credentials" and route to the check-inbox / resend flow.
        raise HTTPException(
            403, "Please verify your email address before logging in. Check your inbox."
        )
    _set_session_cookie(response, user.id, remember=body.remember)
    return UserOut.model_validate(user)


@router.post("/verify-email", response_model=UserOut)
def verify_email(
    body: VerifyEmailIn, response: Response, db: DbSession = Depends(get_db)
) -> UserOut:
    """Validate a verification token, mark the user verified, and log them in."""
    user, reason = consume_token(db, body.token.strip())
    if user is None:
        raise HTTPException(400, _VERIFY_MESSAGES.get(reason, _VERIFY_MESSAGES["invalid"]))
    db.commit()
    _set_session_cookie(response, user.id, remember=True)
    return UserOut.model_validate(user)


@router.post("/resend-verification", response_model=ResendOut)
def resend_verification(body: ResendVerificationIn, db: DbSession = Depends(get_db)) -> ResendOut:
    """Re-send the verification email, rate-limited by a cooldown. The response is
    deliberately uniform so it never reveals whether an account exists."""
    cooldown = settings.email_resend_cooldown_seconds
    generic = ResendOut(
        sent=True,
        retry_after=cooldown,
        message="If that email needs verification, we've sent a new link. Check your inbox.",
    )
    email = body.email.strip().lower()
    if not is_valid_email(email):
        raise HTTPException(400, "Please enter a valid email address.")

    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.email_verified:
        return generic  # nothing to do, but don't leak that

    wait = seconds_until_resend_allowed(db, user)
    if wait > 0:
        raise HTTPException(
            429, f"Please wait {wait}s before requesting another verification email."
        )

    _dispatch_verification(db, user)
    return generic


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    # The clearing cookie must carry the same SameSite/Secure/path attributes as
    # the one it replaces, or the browser treats it as a different cookie and the
    # session cookie is never actually removed.
    samesite, secure = _cookie_samesite_secure()
    response.delete_cookie(settings.auth_cookie, path="/", samesite=samesite, secure=secure)


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
