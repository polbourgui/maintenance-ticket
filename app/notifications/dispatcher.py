from __future__ import annotations

import logging
from collections.abc import Sequence

from fastapi import BackgroundTasks

from app.core.config import Settings
from app.notifications.base import DeliveryResult, Notification, Notifier
from app.notifications.channels import EmailNotifier, LoggingNotifier

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Fans a notification out to every channel; one failing channel never affects the others."""

    def __init__(self, notifiers: Sequence[Notifier]) -> None:
        self.notifiers = list(notifiers)

    def dispatch(self, notification: Notification) -> list[DeliveryResult]:
        results: list[DeliveryResult] = []
        for notifier in self.notifiers:
            try:
                results.append(notifier.send(notification))
            except Exception as exc:
                logger.warning(
                    "notification delivery failed channel=%s event=%s error=%s",
                    notifier.channel,
                    notification.event,
                    type(exc).__name__,
                )
                results.append(DeliveryResult(notifier.channel, delivered=False, detail="error"))
        return results


class BackgroundNotificationScheduler:
    def __init__(
        self, background_tasks: BackgroundTasks, dispatcher: NotificationDispatcher
    ) -> None:
        self._tasks = background_tasks
        self._dispatcher = dispatcher

    def schedule(self, notification: Notification) -> None:
        self._tasks.add_task(self._dispatcher.dispatch, notification)


class ImmediateNotificationScheduler:
    """Synchronous delivery (CLI, scripts)."""

    def __init__(self, dispatcher: NotificationDispatcher) -> None:
        self._dispatcher = dispatcher

    def schedule(self, notification: Notification) -> None:
        self._dispatcher.dispatch(notification)


def build_dispatcher(settings: Settings) -> NotificationDispatcher:
    notifiers: list[Notifier] = []
    if settings.smtp_host:
        notifiers.append(
            EmailNotifier(
                host=settings.smtp_host,
                port=settings.smtp_port,
                sender=settings.smtp_from,
                username=settings.smtp_username,
                password=settings.smtp_password.get_secret_value()
                if settings.smtp_password
                else None,
                starttls=settings.smtp_starttls,
                timeout=settings.notification_timeout_seconds,
            )
        )
    if not notifiers:
        notifiers.append(LoggingNotifier())
    return NotificationDispatcher(notifiers)
