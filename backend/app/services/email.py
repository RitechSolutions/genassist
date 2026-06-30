"""Reusable SMTP email service.

This is the single, reusable primitive for sending transactional/marketing email
(password resets, promotions, notifications, ...). Callers either:

  * call ``EmailService.send_template(...)`` / ``send(...)`` directly (inline), or
  * enqueue ``app.tasks.email_tasks.send_email_task`` for async delivery with retries.

Configuration resolution (per tenant):
  1. Tenant App Settings row of ``type="SMTP"`` (encrypted password decrypted on read).
  2. Global ``settings.SMTP_*`` env vars as a fallback (mirrors the Zendesk pattern).

When ``settings.EMAIL_ENABLED`` is False or no SMTP config is available, the service
logs the rendered email instead of sending — convenient for local dev and CI.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import aiosmtplib
from injector import inject
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from app.core.config.settings import settings
from app.core.utils.encryption_utils import decrypt_key
from app.schemas.dynamic_form_schemas import get_encrypted_fields_for_type
from app.services.app_settings import AppSettingsService

logger = logging.getLogger(__name__)

SMTP_SETTINGS_TYPE = "SMTP"

# Templates live in app/templates/emails/. email.py is app/services/email.py,
# so parents[1] == app/.
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates" / "emails"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n\s*\n\s*\n+")


@dataclass
class SmtpConfig:
    """Resolved SMTP connection + identity settings."""

    host: str
    port: int
    from_email: str
    from_name: str = "GenAssist"
    user: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True  # STARTTLS (port 587)
    timeout: int = 15

    @property
    def implicit_tls(self) -> bool:
        # Port 465 negotiates TLS immediately rather than via STARTTLS.
        return self.port == 465


class EmailNotConfiguredError(RuntimeError):
    """Raised when no usable SMTP configuration is available and sending is required."""


@inject
class EmailService:
    def __init__(self, app_settings_service: AppSettingsService):
        self._app_settings = app_settings_service

    # ------------------------------------------------------------------ config

    async def _resolve_config(self) -> Optional[SmtpConfig]:
        """Resolve SMTP config for the current tenant, falling back to env vars."""
        cfg = await self._config_from_app_settings()
        if cfg:
            return cfg
        return self._config_from_env()

    async def _config_from_app_settings(self) -> Optional[SmtpConfig]:
        try:
            rows = await self._app_settings.repo.get_by_type(SMTP_SETTINGS_TYPE)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not load SMTP App Settings: %s", type(exc).__name__)
            return None

        active = [r for r in (rows or []) if getattr(r, "is_active", 0) == 1]
        if not active:
            return None

        values: Dict[str, Any] = active[0].values if isinstance(active[0].values, dict) else {}
        host = (values.get("smtp_host") or "").strip()
        from_email = (values.get("smtp_from_email") or "").strip()
        if not host or not from_email:
            logger.warning("Tenant SMTP setting present but missing host/from_email; ignoring.")
            return None

        password = values.get("smtp_password")
        if password and "smtp_password" in get_encrypted_fields_for_type(SMTP_SETTINGS_TYPE):
            try:
                password = decrypt_key(password)
            except Exception:
                logger.error("Failed to decrypt tenant smtp_password; check FERNET_KEY parity.")

        return SmtpConfig(
            host=host,
            port=int(values.get("smtp_port") or 587),
            from_email=from_email,
            from_name=(values.get("smtp_from_name") or settings.SMTP_FROM_NAME or "GenAssist"),
            user=(values.get("smtp_user") or None),
            password=(password or None),
            use_tls=bool(values.get("smtp_use_tls", True)),
            timeout=settings.SMTP_TIMEOUT,
        )

    def _config_from_env(self) -> Optional[SmtpConfig]:
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            return None
        return SmtpConfig(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            from_email=settings.SMTP_FROM_EMAIL,
            from_name=settings.SMTP_FROM_NAME or "GenAssist",
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
            timeout=settings.SMTP_TIMEOUT,
        )

    # --------------------------------------------------------------- rendering

    def render_template(
        self, template_name: str, context: Optional[Dict[str, Any]] = None
    ) -> tuple[str, str]:
        """Render ``<template_name>.html`` (and optional ``.txt``) into (html, text).

        If no ``.txt`` template exists, a plain-text version is derived from the HTML.
        """
        context = context or {}
        html_body = _jinja_env.get_template(f"{template_name}.html").render(**context)

        try:
            text_body = _jinja_env.get_template(f"{template_name}.txt").render(**context)
        except TemplateNotFound:
            text_body = self._html_to_text(html_body)

        return html_body, text_body

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = _TAG_RE.sub("", html)
        text = (
            text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )
        return _WS_RE.sub("\n\n", text).strip()

    # ----------------------------------------------------------------- sending

    async def send_template(
        self,
        to: Union[str, Sequence[str]],
        subject: str,
        template_name: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Render a Jinja2 template and send it. Preferred entry point for callers."""
        html_body, text_body = self.render_template(template_name, context)
        return await self.send(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            cc=cc,
            bcc=bcc,
        )

    async def send(
        self,
        to: Union[str, Sequence[str]],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        *,
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Send a single email. Raises EmailNotConfiguredError if no SMTP config and EMAIL_ENABLED."""
        to_list = [to] if isinstance(to, str) else list(to)
        cc_list = list(cc) if cc else []
        bcc_list = list(bcc) if bcc else []

        cfg = await self._resolve_config()

        if not settings.EMAIL_ENABLED or cfg is None:
            reason = "EMAIL_ENABLED is False" if not settings.EMAIL_ENABLED else "no SMTP config"
            logger.info(
                "[email suppressed: %s] to=%s subject=%r\n%s",
                reason,
                to_list,
                subject,
                text_body or self._html_to_text(html_body),
            )
            return {"sent": False, "suppressed": True, "reason": reason, "recipients": to_list}

        message = EmailMessage()
        message["From"] = f"{cfg.from_name} <{cfg.from_email}>"
        message["To"] = ", ".join(to_list)
        if cc_list:
            message["Cc"] = ", ".join(cc_list)
        message["Subject"] = subject
        message.set_content(text_body or self._html_to_text(html_body))
        message.add_alternative(html_body, subtype="html")

        await aiosmtplib.send(
            message,
            recipients=to_list + cc_list + bcc_list,
            hostname=cfg.host,
            port=cfg.port,
            username=cfg.user or None,
            password=cfg.password or None,
            use_tls=cfg.implicit_tls,
            start_tls=cfg.use_tls if not cfg.implicit_tls else False,
            timeout=cfg.timeout,
        )

        logger.info("Email sent to %s (subject=%r) via %s", to_list, subject, cfg.host)
        return {"sent": True, "suppressed": False, "recipients": to_list}