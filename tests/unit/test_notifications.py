from __future__ import annotations

import smtplib
import uuid
from typing import Any

from pydantic import SecretStr

from app.core.config import Settings
from app.models import Site, Ticket, TicketPriority, TicketStatus, User
from app.notifications import (
    DeliveryResult,
    EmailNotifier,
    InMemoryNotifier,
    LoggingNotifier,
    Notification,
    NotificationDispatcher,
    build_dispatcher,
)
from app.notifications.messages import assignment_notification

NOTIF = Notification(
    event="ticket.assigned",
    subject="[ERP-A] Ticket\r\nBcc: attacker@example.org",
    body="Corps",
    summary="ticket assigné",
    email_recipients=("a@example.org", "b@example.org"),
)


class FakeSMTP:
    instances: list[FakeSMTP] = []  # noqa: RUF012

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.messages: list[Any] = []
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        FakeSMTP.instances.append(self)

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def starttls(self, context: object) -> None:
        self.started_tls = True

    def login(self, user: str, password: str) -> None:
        self.logged_in = (user, password)

    def send_message(self, message: Any) -> None:
        self.messages.append(message)


def test_email_notifier() -> None:
    FakeSMTP.instances.clear()
    notifier = EmailNotifier(
        host="smtp.example.org",
        port=587,
        sender="noreply@example.org",
        username="u",
        password="p",
        smtp_factory=FakeSMTP,  # type: ignore[arg-type]
    )
    result = notifier.send(NOTIF)
    assert result == DeliveryResult("email", delivered=True)
    smtp = FakeSMTP.instances[0]
    assert smtp.started_tls
    assert smtp.logged_in == ("u", "p")
    msg = smtp.messages[0]
    assert msg["Bcc"] == "a@example.org, b@example.org"
    assert "\n" not in msg["Subject"]  # no header injection
    assert msg["Subject"] == "[ERP-A] Ticket Bcc: attacker@example.org"


def test_email_notifier_skips_without_recipient() -> None:
    notifier = EmailNotifier(host="h", port=25, sender="s@example.org", smtp_factory=FakeSMTP)  # type: ignore[arg-type]
    n = Notification(event="e", subject="s", body="b", summary="p")
    assert notifier.send(n).delivered is False


class BrokenNotifier:
    channel = "broken"

    def send(self, notification: Notification) -> DeliveryResult:
        raise ConnectionError("SMTP down")


def test_dispatcher_isolates_channel_failures() -> None:
    memory = InMemoryNotifier()
    dispatcher = NotificationDispatcher([BrokenNotifier(), memory])
    results = dispatcher.dispatch(NOTIF)
    assert results == [
        DeliveryResult("broken", delivered=False, detail="error"),
        DeliveryResult("memory", delivered=True),
    ]
    assert memory.sent == [NOTIF]


def test_build_dispatcher_from_settings() -> None:
    secret = SecretStr("k" * 40)
    default = build_dispatcher(Settings(secret_key=secret))
    assert [type(n) for n in default.notifiers] == [LoggingNotifier]
    full = build_dispatcher(
        Settings(
            secret_key=secret,
            smtp_host="smtp.example.org",
        )
    )
    assert [n.channel for n in full.notifiers] == ["email"]


def test_smtp_factory_default_is_smtplib() -> None:
    notifier = EmailNotifier(host="h", port=25, sender="s@example.org")
    assert notifier._smtp_factory is smtplib.SMTP


def test_message_location_and_long_description() -> None:
    site = Site(code="ERP-1", name="Médiathèque")
    assignee = User(email="tech@example.org", full_name="Tech")
    ticket = Ticket(
        id=uuid.uuid4(),
        title="Fuite",
        description="x" * 5000,
        priority=TicketPriority.LOW,
        status=TicketStatus.TODO,
        location_room="Hall",
        location_building=None,
        location_floor="RDC",
        location_details="près de\nl'issue Est",
    )
    ticket.site = site
    ticket.assignee_user = assignee
    message = assignment_notification(ticket)
    assert "Localisation : RDC · Hall (près de l'issue Est)\n" in message.body
    assert "Priorité : Basse" in message.body
    assert "x" * 999 + "…" in message.body
    assert "x" * 1000 not in message.body
