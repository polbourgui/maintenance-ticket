from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.errors import NotFoundError
from app.domain.rbac import AccessPolicy, Permission
from app.models import Site, TicketStatus
from app.repositories import UnitOfWork
from app.schemas.reports import DashboardReport, SiteStats

_REPORT_SITE_LIMIT = 500


class ReportService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def dashboard(self, policy: AccessPolicy) -> DashboardReport:
        policy.require(Permission.REPORT_READ)
        sites, _ = self.uow.sites.search(
            offset=0, limit=_REPORT_SITE_LIMIT, restrict_to=policy.accessible_site_ids()
        )
        stats = [self._site_stats(site) for site in sites]
        totals = {status: sum(s.by_status[status] for s in stats) for status in TicketStatus}
        return DashboardReport(generated_at=datetime.now(UTC), totals=totals, sites=stats)

    def site(self, policy: AccessPolicy, site_id: uuid.UUID) -> SiteStats:
        policy.require(Permission.REPORT_READ)
        policy.require_site(site_id)
        site = self.uow.sites.get(site_id)
        if site is None:
            raise NotFoundError("Site not found")
        return self._site_stats(site)

    def _site_stats(self, site: Site) -> SiteStats:
        raw = self.uow.tickets.stats_for_site(site.id)
        total = sum(raw.by_status.values())
        return SiteStats(
            site_id=site.id,
            site_code=site.code,
            site_name=site.name,
            total=total,
            open=total - raw.by_status[TicketStatus.DONE],
            by_status=raw.by_status,
            open_by_priority=raw.by_priority,
            archived=raw.archived,
            avg_resolution_hours=raw.avg_resolution_hours,
        )
