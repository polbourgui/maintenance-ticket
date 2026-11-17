from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import TicketPriority, TicketStatus


class SiteStats(BaseModel):
    site_id: uuid.UUID
    site_code: str
    site_name: str
    total: int
    open: int
    by_status: dict[TicketStatus, int]
    open_by_priority: dict[TicketPriority, int]
    archived: int
    avg_resolution_hours: float | None


class DashboardReport(BaseModel):
    generated_at: datetime
    totals: dict[TicketStatus, int]
    sites: list[SiteStats]


class NotificationTestResult(BaseModel):
    channel: str
    delivered: bool
    detail: str
