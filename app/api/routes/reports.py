from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import Policy, ReportServiceDep
from app.schemas.reports import DashboardReport, SiteStats

router = APIRouter(prefix="/reports", tags=["Reporting"])


@router.get("/dashboard", response_model=DashboardReport)
def dashboard(policy: Policy, reports: ReportServiceDep) -> DashboardReport:
    """Statistics for every site visible to the current user."""
    return reports.dashboard(policy)


@router.get("/sites/{site_id}", response_model=SiteStats)
def site_report(site_id: uuid.UUID, policy: Policy, reports: ReportServiceDep) -> SiteStats:
    return reports.site(policy, site_id)
