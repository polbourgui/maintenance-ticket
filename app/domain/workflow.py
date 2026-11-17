"""Ticket status state machine."""

from __future__ import annotations

from app.core.errors import BusinessRuleError
from app.models import Ticket, TicketStatus

ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.TODO: frozenset({TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED}),
    TicketStatus.IN_PROGRESS: frozenset(
        {TicketStatus.TODO, TicketStatus.BLOCKED, TicketStatus.DONE}
    ),
    TicketStatus.BLOCKED: frozenset({TicketStatus.TODO, TicketStatus.IN_PROGRESS}),
    TicketStatus.DONE: frozenset({TicketStatus.IN_PROGRESS}),  # reopening (admin only)
}

STATUSES_REQUIRING_ASSIGNEE = frozenset({TicketStatus.IN_PROGRESS, TicketStatus.DONE})


def validate_transition(ticket: Ticket, target: TicketStatus, comment: str | None) -> None:
    if ticket.is_archived:
        raise BusinessRuleError("Archived tickets are read-only")
    if target == ticket.status:
        raise BusinessRuleError(f"Ticket is already '{target.value}'")
    if target not in ALLOWED_TRANSITIONS[ticket.status]:
        raise BusinessRuleError(
            f"Transition '{ticket.status.value}' -> '{target.value}' is not allowed"
        )
    if target in STATUSES_REQUIRING_ASSIGNEE and ticket.assignee_type is None:
        raise BusinessRuleError(f"A ticket must be assigned before moving to '{target.value}'")
    if target is TicketStatus.BLOCKED and not (comment and comment.strip()):
        raise BusinessRuleError("A reason (comment) is required to block a ticket")


def is_reopening(ticket: Ticket, target: TicketStatus) -> bool:
    return ticket.status is TicketStatus.DONE and target is not TicketStatus.DONE
