from __future__ import annotations

import logging
import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage

from app.notifications.base import DeliveryResult, Notification

logger = logging.getLogger(__name__)


class EmailNotifier:
    channel = "email"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        starttls: bool = True,
        timeout: float = 5.0,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._starttls = starttls
        self._timeout = timeout
        self._smtp_factory = smtp_factory

    def send(self, notification: Notification) -> DeliveryResult:
        if not notification.email_recipients:
            return DeliveryResult(self.channel, delivered=False, detail="no recipient")
        message = EmailMessage()
        # Header injection guard: subjects come partly from user input.
        message["Subject"] = " ".join(notification.subject.split())
        message["From"] = self._sender
        message["To"] = self._sender
        message["Bcc"] = ", ".join(notification.email_recipients)  # recipients don't see each other
        message.set_content(notification.body)
        with self._smtp_factory(self._host, self._port, timeout=self._timeout) as smtp:
            if self._starttls:
                smtp.starttls(context=ssl.create_default_context())
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(message)
        return DeliveryResult(self.channel, delivered=True)


class LoggingNotifier:
    """Fallback when no channel is configured (development). Logs no personal data."""

    channel = "log"

    def send(self, notification: Notification) -> DeliveryResult:
        logger.info("notification event=%s text=%s", notification.event, notification.summary)
        return DeliveryResult(self.channel, delivered=True)


class InMemoryNotifier:
    """Captures notifications; used by tests and the notification self-test."""

    channel = "memory"

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def send(self, notification: Notification) -> DeliveryResult:
        self.sent.append(notification)
        return DeliveryResult(self.channel, delivered=True)
