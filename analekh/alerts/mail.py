"""Mail to any recipient over the same SMTP settings as the alerts (`notify.send_email`).

The body can carry a one-time code, so it is never logged; a failure logs only the exception type.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import unquote, urlparse

from analekh.config import get_settings

log = logging.getLogger(__name__)


def send_mail(to: str, subject: str, body: str) -> bool:
    """True when the message was handed to the SMTP server; False when SMTP is not set up or
    sending failed. SMTP_URL looks like smtp://user:pass@host:587; the sender is SMTP_FROM, else
    the SMTP user name."""
    s = get_settings()
    if not s.smtp_url:
        return False
    url = urlparse(s.smtp_url)
    sender = s.smtp_from or unquote(url.username or "")
    if not sender:
        return False
    msg = EmailMessage()
    msg["Subject"], msg["To"], msg["From"] = subject, to, sender
    msg.set_content(body)
    try:
        with smtplib.SMTP(url.hostname or "localhost", url.port or 587, timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())  # verify cert and host name
            if url.username:
                smtp.login(unquote(url.username), unquote(url.password or ""))
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("mail not sent: %s %s", type(exc).__name__, getattr(exc, "smtp_code", ""))
        return False
    return True
