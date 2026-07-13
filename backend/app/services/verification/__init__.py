"""Email-verification domain logic: issuing, sending, and consuming single-use
tokens, plus resend cooldown and email-address validation.

Kept separate from the HTTP layer so it's unit-testable and the endpoints stay thin.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from app.config import get_settings
from app.models import EmailVerificationToken, User
from app.services.auth import hash_token, new_verification_token
from app.services.email import EmailMessage, send_email

# Pragmatic RFC-5321-ish check: one @, a local part, and a dotted domain with a
# 2+ char TLD. Rejects the common malformed cases without the false negatives of
# an over-strict regex.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def is_valid_email(email: str) -> bool:
    email = email.strip()
    return bool(email) and len(email) <= 254 and _EMAIL_RE.match(email) is not None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def seconds_until_resend_allowed(db: DbSession, user: User) -> int:
    """0 if a new verification email may be sent now, else seconds to wait.
    Prevents duplicate emails being spammed."""
    latest = db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .limit(1)
    )
    if latest is None:
        return 0
    cooldown = get_settings().email_resend_cooldown_seconds
    elapsed = (_utcnow() - _aware(latest.created_at)).total_seconds()
    return max(0, int(cooldown - elapsed))


def issue_token(db: DbSession, user: User) -> str:
    """Create a fresh verification token, superseding any earlier unused ones so
    only the newest link is valid. Returns the raw token (store only its hash)."""
    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=_utcnow())
    )
    raw = new_verification_token()
    ttl = get_settings().email_verification_ttl_hours
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=_utcnow() + timedelta(hours=ttl),
        )
    )
    db.flush()
    return raw


def consume_token(db: DbSession, raw: str) -> tuple[User | None, str]:
    """Validate and burn a verification token.

    Returns ``(user, "ok")`` on success, or ``(None, reason)`` where reason is
    ``"invalid"`` (unknown/garbage), ``"used"`` (already consumed), or ``"expired"``.
    """
    if not raw:
        return None, "invalid"
    row = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(raw)
        )
    )
    if row is None:
        return None, "invalid"
    if row.used_at is not None:
        return None, "used"
    if _aware(row.expires_at) < _utcnow():
        return None, "expired"

    user = db.get(User, row.user_id)
    if user is None:
        return None, "invalid"
    row.used_at = _utcnow()
    if not user.email_verified:
        user.email_verified = True
        user.verified_at = _utcnow()
    db.flush()
    return user, "ok"


def send_verification_email(user: User, raw_token: str) -> None:
    """Compose and dispatch the verification email. Raises ``EmailError`` on
    delivery failure (callers decide whether that should fail the request)."""
    settings = get_settings()
    link = f"{settings.frontend_url.rstrip('/')}/verify?token={raw_token}"
    hours = settings.email_verification_ttl_hours
    name = user.name.strip() or "there"
    send_email(
        EmailMessage(
            to=user.email,
            subject="Confirm your physIQal email",
            html=_html(name, link, hours),
            text=(
                f"Hi {name},\n\nConfirm your email to activate your physIQal account:\n"
                f"{link}\n\nThis link expires in {hours} hours. "
                "If you didn't create an account, you can ignore this email."
            ),
        )
    )


def _html(name: str, link: str, hours: int) -> str:
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;background:#0b0b0b;padding:32px 0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr><td align="center">
        <table role="presentation" width="440" cellpadding="0" cellspacing="0"
               style="background:#161616;border:1px solid #2a2a2a;border-radius:14px;overflow:hidden;">
          <tr><td style="padding:32px 32px 8px;">
            <div style="font-size:18px;font-weight:700;letter-spacing:2px;color:#ededed;">
              PHYS<span style="color:#8a8a8a;">IQ</span>AL
            </div>
          </td></tr>
          <tr><td style="padding:12px 32px 8px;color:#ededed;font-size:20px;font-weight:600;">
            Confirm your email
          </td></tr>
          <tr><td style="padding:4px 32px 20px;color:#9a9a9a;font-size:14px;line-height:1.6;">
            Hi {name}, welcome to physIQal. Confirm this address to activate your account
            and start analysing your lifts.
          </td></tr>
          <tr><td style="padding:0 32px 28px;">
            <a href="{link}"
               style="display:inline-block;background:#ededed;color:#0a0a0a;text-decoration:none;
                      font-weight:600;font-size:14px;padding:12px 22px;border-radius:8px;">
              Verify email
            </a>
          </td></tr>
          <tr><td style="padding:0 32px 28px;color:#6e6e6e;font-size:12px;line-height:1.6;">
            This link expires in {hours} hours. If the button doesn't work, paste this into your browser:<br>
            <a href="{link}" style="color:#8a8a8a;word-break:break-all;">{link}</a><br><br>
            If you didn't create a physIQal account, you can safely ignore this email.
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""
