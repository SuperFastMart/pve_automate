import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import aiosmtplib
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select

from app.config import get_effective_settings
from app.database import async_session
from app.models.vm_request import VMRequest

logger = logging.getLogger(__name__)

# Jinja2 template environment — loaded once
_template_dir = Path(__file__).resolve().parent.parent / "templates" / "email"
_jinja_env = Environment(loader=FileSystemLoader(str(_template_dir)), autoescape=True)


def render_template(template_name: str, **context) -> str:
    """Render an HTML email template with the given context."""
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


class EmailService:
    """Async SMTP email sender."""

    def __init__(
        self, host: str, port: int, user: str, password: str,
        use_tls: bool, from_addr: str,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.from_addr = from_addr

    async def send(self, to: str, subject: str, html_body: str) -> None:
        """Send an HTML email to a single recipient."""
        msg = MIMEMultipart("alternative")
        msg["From"] = self.from_addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        kwargs = {
            "hostname": self.host,
            "port": self.port,
            "timeout": 30,
        }
        if self.use_tls:
            kwargs["start_tls"] = True
        if self.user and self.password:
            kwargs["username"] = self.user
            kwargs["password"] = self.password

        await aiosmtplib.send(msg, **kwargs)
        logger.info(f"Email sent to {to}: {subject}")


async def get_email_service(db) -> Optional[EmailService]:
    """Build EmailService from effective settings. Returns None if unconfigured."""
    settings = await get_effective_settings(db, group="smtp")
    host = settings.get("SMTP_HOST", "")
    if not host:
        return None

    port = int(settings.get("SMTP_PORT", "587"))
    user = settings.get("SMTP_USER", "")
    password = settings.get("SMTP_PASSWORD", "")
    use_tls_raw = settings.get("SMTP_USE_TLS", "true")
    use_tls = str(use_tls_raw).lower() in ("true", "1", "yes")
    from_addr = settings.get("EMAIL_FROM", "peevinator@example.com")

    return EmailService(
        host=host, port=port, user=user, password=password,
        use_tls=use_tls, from_addr=from_addr,
    )


# ── Fire-and-forget helper functions ──────────────────────────────────


async def send_request_received(request_id: int) -> None:
    """Background task: send 'request received' email to requestor."""
    try:
        async with async_session() as db:
            svc = await get_email_service(db)
            if not svc:
                return
            result = await db.execute(
                select(VMRequest).where(VMRequest.id == request_id)
            )
            vm = result.scalar_one_or_none()
            if not vm:
                return

            html = render_template(
                "request_received.html",
                vm=vm,
            )
            await svc.send(
                to=vm.requestor_email,
                subject=f"VM Request Received: {vm.vm_name}",
                html_body=html,
            )
    except Exception as e:
        logger.warning(f"Failed to send 'request received' email for request {request_id}: {e}")


async def send_vm_ready(request_id: int) -> None:
    """Background task: send 'VM ready' email to requestor."""
    try:
        async with async_session() as db:
            svc = await get_email_service(db)
            if not svc:
                return
            result = await db.execute(
                select(VMRequest).where(VMRequest.id == request_id)
            )
            vm = result.scalar_one_or_none()
            if not vm:
                return

            html = render_template(
                "vm_ready.html",
                vm=vm,
            )
            await svc.send(
                to=vm.requestor_email,
                subject=f"VM Ready: {vm.vm_name}",
                html_body=html,
            )
    except Exception as e:
        logger.warning(f"Failed to send 'VM ready' email for request {request_id}: {e}")


async def send_request_rejected(request_id: int) -> None:
    """Background task: send 'request rejected' email to requestor."""
    try:
        async with async_session() as db:
            svc = await get_email_service(db)
            if not svc:
                return
            result = await db.execute(
                select(VMRequest).where(VMRequest.id == request_id)
            )
            vm = result.scalar_one_or_none()
            if not vm:
                return

            html = render_template(
                "request_rejected.html",
                vm=vm,
            )
            await svc.send(
                to=vm.requestor_email,
                subject=f"VM Request Rejected: {vm.vm_name}",
                html_body=html,
            )
    except Exception as e:
        logger.warning(f"Failed to send 'request rejected' email for request {request_id}: {e}")


async def send_provisioning_failed(request_id: int) -> None:
    """Background task: send 'provisioning failed' email to requestor."""
    try:
        async with async_session() as db:
            svc = await get_email_service(db)
            if not svc:
                return
            result = await db.execute(
                select(VMRequest).where(VMRequest.id == request_id)
            )
            vm = result.scalar_one_or_none()
            if not vm:
                return

            html = render_template(
                "provisioning_failed.html",
                vm=vm,
            )
            await svc.send(
                to=vm.requestor_email,
                subject=f"VM Provisioning Failed: {vm.vm_name}",
                html_body=html,
            )
    except Exception as e:
        logger.warning(f"Failed to send 'provisioning failed' email for request {request_id}: {e}")
