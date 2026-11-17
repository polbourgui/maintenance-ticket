"""Builders turning domain events into notifications (French, end-user facing)."""

from __future__ import annotations

from app.models import Ticket, TicketStatus
from app.notifications.base import Notification

STATUS_LABELS: dict[TicketStatus, str] = {
    TicketStatus.TODO: "À faire",
    TicketStatus.IN_PROGRESS: "En cours",
    TicketStatus.BLOCKED: "Bloqué",
    TicketStatus.DONE: "Terminé",
}


def _sanitize(text: str, max_len: int = 120) -> str:
    """Single line, bounded length (used in e-mail subjects and log summaries)."""
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= max_len else cleaned[: max_len - 1] + "…"


def _ref(ticket: Ticket) -> str:
    return f"#{str(ticket.id)[:8]}"


def _assignee_email(ticket: Ticket) -> str | None:
    if ticket.assignee_user is not None:
        return ticket.assignee_user.email
    if ticket.assignee_provider is not None:
        return ticket.assignee_provider.email
    return None


def assignment_notification(ticket: Ticket) -> Notification:
    title = _sanitize(ticket.title)
    recipient = _assignee_email(ticket)
    kind = "prestataire externe" if ticket.assignee_provider_id else "technicien"
    return Notification(
        event="ticket.assigned",
        subject=f"[{ticket.site.code}] Ticket {_ref(ticket)} vous a été assigné : {title}",
        body=(
            "Bonjour,\n\n"
            f"Le ticket {_ref(ticket)} « {title} » vous a été assigné.\n"
            f"Établissement : {ticket.site.name} ({ticket.site.code})\n"
            f"Localisation : {ticket.location_room}\n"
            f"Priorité : {ticket.priority.value}\n"
            f"Statut : {STATUS_LABELS[ticket.status]}\n"
        ),
        summary=(
            f"📌 [{ticket.site.code}] Ticket {_ref(ticket)} « {title} » "
            f"assigné à un {kind} (priorité {ticket.priority.value})."
        ),
        email_recipients=(recipient,) if recipient else (),
    )


def status_change_notification(
    ticket: Ticket, previous: TicketStatus, comment: str | None
) -> Notification:
    title = _sanitize(ticket.title)
    recipients = {ticket.created_by.email}
    if (email := _assignee_email(ticket)) is not None:
        recipients.add(email)
    old, new = STATUS_LABELS[previous], STATUS_LABELS[ticket.status]
    body = (
        "Bonjour,\n\n"
        f"Le ticket {_ref(ticket)} « {title} » est passé de « {old} » à « {new} ».\n"
        f"Établissement : {ticket.site.name} ({ticket.site.code})\n"
    )
    if comment:
        body += f"Commentaire : {comment}\n"
    return Notification(
        event="ticket.status_changed",
        subject=f"[{ticket.site.code}] Ticket {_ref(ticket)} : {old} → {new}",
        body=body,
        summary=f"🔄 [{ticket.site.code}] Ticket {_ref(ticket)} « {title} » : {old} → {new}.",
        email_recipients=tuple(sorted(r for r in recipients if not r.endswith(".invalid"))),
    )


def test_notification(recipient_email: str) -> Notification:
    return Notification(
        event="notification.test",
        subject="[ERP Maintenance] Notification de test",
        body="Ceci est une notification de test. La configuration des alertes fonctionne.",
        summary="✅ Notification de test : la configuration des alertes fonctionne.",
        email_recipients=(recipient_email,),
    )
