from __future__ import annotations

import json
import smtplib
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.notifications import (
    DeliveryResult,
    DiscordWebhookNotifier,
    EmailNotifier,
    InMemoryNotifier,
    LoggingNotifier,
    Notification,
    NotificationDispatcher,
    build_dispatcher,
)

NOTIF = Notification(
    event="ticket.assigned",
    subject="[ERP-A] Ticket\r\nBcc: attacker@example.org",
    body="Corps",
    public_text="@everyone ticket assigné",
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
    n = Notification(event="e", subject="s", body="b", public_text="p")
    assert notifier.send(n).delivered is False


def test_discord_notifier_payload() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(204)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/x", client=client)
    assert notifier.send(NOTIF).delivered
    payload = json.loads(captured[0].content)
    assert payload["content"] == "@everyone ticket assigné"
    assert payload["allowed_mentions"] == {"parse": []}  # mass mentions neutralised
    assert "a@example.org" not in captured[0].content.decode()  # no PII on Discord


def test_discord_notifier_raises_on_http_error() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(500)))
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/x", client=client)
    with pytest.raises(httpx.HTTPStatusError):
        notifier.send(NOTIF)


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
            discord_webhook_url=SecretStr("https://discord.com/api/webhooks/1/x"),
        )
    )
    assert [n.channel for n in full.notifiers] == ["email", "discord"]


def test_smtp_factory_default_is_smtplib() -> None:
    notifier = EmailNotifier(host="h", port=25, sender="s@example.org")
    assert notifier._smtp_factory is smtplib.SMTP
