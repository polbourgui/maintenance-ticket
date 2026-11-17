/**
 * Mirror of the backend RBAC matrix (app/domain/rbac.py), used ONLY to adapt the UI.
 * The API enforces every rule; hiding a button is never a security control.
 */
import type { Role, Ticket, TicketStatus, User } from "../api/types";

const isAdmin = (user: User) => user.role === "admin";
const isStaff = (user: User) => user.role === "admin" || user.role === "technician";

export const can = {
  manage: isAdmin,
  assign: isAdmin,
  archive: isAdmin,
  reopen: isAdmin,
  readProviders: isStaff,
  editTicket: isStaff,
  uploadPhoto: isStaff,
  changeStatus: (user: User, ticket: Ticket) =>
    isAdmin(user) ||
    (user.role === "technician" &&
      ticket.assignee?.type === "technician" &&
      ticket.assignee.id === user.id),
};

export const TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  todo: ["in_progress", "blocked"],
  in_progress: ["todo", "blocked", "done"],
  blocked: ["todo", "in_progress"],
  done: ["in_progress"],
};

/** Status buttons to offer for this ticket and user. */
export function availableTransitions(user: User, ticket: Ticket): TicketStatus[] {
  if (ticket.archived_at || !can.changeStatus(user, ticket)) return [];
  return TRANSITIONS[ticket.status].filter((target) => {
    if (ticket.status === "done") return can.reopen(user);
    if ((target === "in_progress" || target === "done") && !ticket.assignee) return false;
    return true;
  });
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrateur",
  technician: "Technicien",
  client: "Client",
};
