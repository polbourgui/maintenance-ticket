from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.errors import BusinessRuleError
from app.domain.workflow import ALLOWED_TRANSITIONS, is_reopening, validate_transition
from app.models import Ticket, TicketPriority, TicketStatus


def _ticket(status: TicketStatus, *, assigned: bool = True, archived: bool = False) -> Ticket:
    return Ticket(
        site_id=uuid.uuid4(),
        title="t",
        description="d",
        priority=TicketPriority.LOW,
        status=status,
        location_room="r",
        created_by_id=uuid.uuid4(),
        assignee_user_id=uuid.uuid4() if assigned else None,
        archived_at=datetime.now(UTC) if archived else None,
    )


@pytest.mark.parametrize(
    ("source", "target"),
    [(s, t) for s, targets in ALLOWED_TRANSITIONS.items() for t in targets],
)
def test_allowed_transitions(source: TicketStatus, target: TicketStatus) -> None:
    validate_transition(_ticket(source), target, comment="reason")


@pytest.mark.parametrize(
    ("source", "target"),
    [(s, t) for s in TicketStatus for t in TicketStatus if t not in ALLOWED_TRANSITIONS[s]],
)
def test_forbidden_transitions(source: TicketStatus, target: TicketStatus) -> None:
    with pytest.raises(BusinessRuleError):
        validate_transition(_ticket(source), target, comment="reason")


def test_blocking_requires_comment() -> None:
    with pytest.raises(BusinessRuleError, match="reason"):
        validate_transition(_ticket(TicketStatus.TODO), TicketStatus.BLOCKED, comment="   ")


@pytest.mark.parametrize("target", [TicketStatus.IN_PROGRESS])
def test_work_requires_assignee(target: TicketStatus) -> None:
    with pytest.raises(BusinessRuleError, match="assigned"):
        validate_transition(_ticket(TicketStatus.TODO, assigned=False), target, comment=None)


def test_archived_is_read_only() -> None:
    with pytest.raises(BusinessRuleError, match="Archived"):
        validate_transition(
            _ticket(TicketStatus.DONE, archived=True), TicketStatus.IN_PROGRESS, None
        )


def test_is_reopening() -> None:
    assert is_reopening(_ticket(TicketStatus.DONE), TicketStatus.IN_PROGRESS)
    assert not is_reopening(_ticket(TicketStatus.BLOCKED), TicketStatus.IN_PROGRESS)
