"""Email delivery.

A tiny provider abstraction with implementations for Resend (default), SendGrid,
and SMTP — plus a ``console`` fallback that logs instead of sending, used
automatically when the selected provider has no credentials (so local dev and
tests work without real email). Everything is stdlib-only (``urllib`` for the
REST providers, ``smtplib`` for SMTP): no extra dependencies.

Usage::

    from app.services.email import send_email, EmailMessage
    send_email(EmailMessage(to=..., subject=..., html=..., text=...))
"""
from __future__ import annotations

import json
import logging
import smtplib
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from typing import Protocol

from app.config import Settings, get_settings

logger = logging.getLogger("kinesis.email")


class EmailError(RuntimeError):
    """Raised when an email could not be handed off to the provider."""


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str = ""


# A test/dev outbox: the console provider records what it "sent" here so flows can
# be asserted end-to-end without a real provider. Never populated in production.
outbox: list[EmailMessage] = []


class EmailProvider(Protocol):
    def send(self, msg: EmailMessage) -> None: ...


class ConsoleProvider:
    """Logs the message (and records it in ``outbox``) instead of sending."""

    def send(self, msg: EmailMessage) -> None:
        outbox.append(msg)
        logger.info("[email:console] To: %s | %s\n%s", msg.to, msg.subject, msg.text or msg.html)


class ResendProvider:
    """https://resend.com — POST https://api.resend.com/emails"""

    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    def send(self, msg: EmailMessage) -> None:
        payload = {
            "from": self._sender,
            "to": [msg.to],
            "subject": msg.subject,
            "html": msg.html,
        }
        if msg.text:
            payload["text"] = msg.text
        _post_json(
            "https://api.resend.com/emails",
            payload,
            {"Authorization": f"Bearer {self._api_key}"},
        )


class SendGridProvider:
    """https://sendgrid.com — POST https://api.sendgrid.com/v3/mail/send"""

    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = _parse_sender(sender)

    def send(self, msg: EmailMessage) -> None:
        content = [{"type": "text/html", "value": msg.html}]
        if msg.text:
            content.insert(0, {"type": "text/plain", "value": msg.text})
        payload = {
            "personalizations": [{"to": [{"email": msg.to}]}],
            "from": self._sender,
            "subject": msg.subject,
            "content": content,
        }
        _post_json(
            "https://api.sendgrid.com/v3/mail/send",
            payload,
            {"Authorization": f"Bearer {self._api_key}"},
            expect_json=False,
        )


class SMTPProvider:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def send(self, msg: EmailMessage) -> None:
        s = self._s
        mime = MimeMessage()
        mime["From"] = s.email_from
        mime["To"] = msg.to
        mime["Subject"] = msg.subject
        mime.set_content(msg.text or "Please view this message in an HTML-capable client.")
        mime.add_alternative(msg.html, subtype="html")
        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
                if s.smtp_starttls:
                    server.starttls()
                if s.smtp_user:
                    server.login(s.smtp_user, s.smtp_password or "")
                server.send_message(mime)
        except (smtplib.SMTPException, OSError) as exc:  # pragma: no cover - network
            raise EmailError(f"SMTP send failed: {exc}") from exc


def _parse_sender(sender: str) -> dict:
    """Turn "Name <addr@x>" or "addr@x" into SendGrid's {email,name} shape."""
    if "<" in sender and ">" in sender:
        name, addr = sender.split("<", 1)
        return {"email": addr.rstrip(">").strip(), "name": name.strip()}
    return {"email": sender.strip()}


def _post_json(url: str, payload: dict, headers: dict, expect_json: bool = True) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed https hosts
            if resp.status >= 300:
                raise EmailError(f"Provider returned HTTP {resp.status}")
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        body = exc.read().decode("utf-8", "replace")[:500]
        raise EmailError(f"Provider HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network
        raise EmailError(f"Could not reach email provider: {exc.reason}") from exc


def _build_provider(settings: Settings) -> EmailProvider:
    provider = (settings.email_provider or "resend").lower()
    if provider == "resend" and settings.resend_api_key:
        return ResendProvider(settings.resend_api_key, settings.email_from)
    if provider == "sendgrid" and settings.sendgrid_api_key:
        return SendGridProvider(settings.sendgrid_api_key, settings.email_from)
    if provider == "smtp" and settings.smtp_host:
        return SMTPProvider(settings)
    if provider != "console":
        logger.warning(
            "Email provider %r has no credentials configured — falling back to console "
            "delivery (links are logged, not emailed).",
            provider,
        )
    return ConsoleProvider()


def get_email_provider() -> EmailProvider:
    return _build_provider(get_settings())


def send_email(msg: EmailMessage) -> None:
    """Send a message via the configured provider. Raises ``EmailError`` on failure."""
    get_email_provider().send(msg)
