from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_dispatcher, get_session, require
from app.domain.rbac import AccessPolicy, Permission
from app.notifications import NotificationDispatcher
from app.notifications.messages import test_notification
from app.schemas.reports import NotificationTestResult

router = APIRouter(tags=["Système"])


@router.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.post("/notifications/test", response_model=list[NotificationTestResult])
def send_test_notification(
    policy: Annotated[AccessPolicy, Depends(require(Permission.NOTIFICATION_TEST))],
    dispatcher: Annotated[NotificationDispatcher, Depends(get_dispatcher)],
) -> list[NotificationTestResult]:
    """Send a test notification on every configured channel (e-mail to the caller, Discord)."""
    results = dispatcher.dispatch(test_notification(policy.user.email))
    return [
        NotificationTestResult(channel=r.channel, delivered=r.delivered, detail=r.detail)
        for r in results
    ]
