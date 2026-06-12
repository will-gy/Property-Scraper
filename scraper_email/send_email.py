"""Transport only: send a prebuilt HTML email via Gmail SMTP.

HTML is built by ``email_builder``; this class just delivers it.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from settings import get_settings

logger = logging.getLogger(__name__)


class SendEmail:
    def __init__(self, to_addr: list[str], bcc_addr: list[str]) -> None:
        settings = get_settings()
        self._gmail_user = settings.gmail_user
        self._gmail_password = settings.gmail_password
        self._from_addr = settings.gmail_from_addr
        self._to_addr = to_addr or []
        self._bcc_addr = bcc_addr or []

    def send(self, subject: str, html: str) -> None:
        message = MIMEMultipart("alternative")
        message["From"] = self._from_addr
        message["To"] = ", ".join(self._to_addr)
        message["Subject"] = subject
        message.attach(MIMEText(html, "html"))

        recipients = self._to_addr + self._bcc_addr
        with smtplib.SMTP("smtp.gmail.com", 587) as session:
            session.starttls()
            session.login(self._gmail_user, self._gmail_password)
            session.sendmail(self._from_addr, recipients, message.as_string())
        logger.info("Mail sent to %d recipients", len(recipients))
