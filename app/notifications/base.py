from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Notification:
    """Channel-agnostic message, built *before* the DB session closes (plain data only).

    GDPR: ``email_recipients`` are only used by the e-mail channel. ``summary`` is a one-line
    description written to logs and must never contain personal data.
    """

    event: str
    subject: str
    body: str
    summary: str
    email_recipients: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    channel: str
    delivered: bool
    detail: str = ""


class Notifier(Protocol):
    channel: str

    def send(self, notification: Notification) -> DeliveryResult: ...


class NotificationScheduler(Protocol):
    """Defers delivery so that slow SMTP calls never block the HTTP response."""

    def schedule(self, notification: Notification) -> None: ...
