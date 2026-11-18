import type { PhotoKind, TicketEvent, TicketPriority, TicketStatus } from "../api/types";

export const STATUS_LABELS: Record<TicketStatus, string> = {
  todo: "À faire",
  in_progress: "En cours",
  blocked: "Bloqué",
  done: "Terminé",
};

export const STATUS_ACTIONS: Record<TicketStatus, string> = {
  todo: "Remettre à faire",
  in_progress: "Démarrer / reprendre",
  blocked: "Bloquer",
  done: "Terminer",
};

export const PRIORITY_LABELS: Record<TicketPriority, string> = {
  low: "Basse",
  medium: "Moyenne",
  high: "Haute",
  critical: "Critique",
};

export const PHOTO_KIND_LABELS: Record<PhotoKind, string> = { before: "Avant", after: "Après" };

export const STATUSES = Object.keys(STATUS_LABELS) as TicketStatus[];
export const PRIORITIES = Object.keys(PRIORITY_LABELS) as TicketPriority[];

const FIELD_LABELS: Record<string, string> = {
  title: "titre",
  description: "description",
  priority: "priorité",
  location_building: "localisation",
  location_floor: "localisation",
  location_room: "localisation",
  location_details: "localisation",
};

export function describeEvent(event: TicketEvent): string {
  switch (event.event_type) {
    case "created":
      return "Ticket créé";
    case "updated": {
      const fields = Array.isArray(event.details.fields) ? (event.details.fields as string[]) : [];
      const labels = [...new Set(fields.map((f) => FIELD_LABELS[f] ?? f))];
      return labels.length ? `Ticket modifié : ${labels.join(", ")}` : "Ticket modifié";
    }
    case "assigned":
      return event.details.assignee_type === "provider"
        ? "Assigné à un prestataire externe"
        : "Assigné à un technicien";
    case "unassigned":
      return "Assignation retirée";
    case "status_changed":
      return `Statut : ${event.from_status ? STATUS_LABELS[event.from_status] : "?"} → ${
        event.to_status ? STATUS_LABELS[event.to_status] : "?"
      }`;
    case "photo_added":
      return `Photo « ${event.details.kind === "after" ? "après" : "avant"} » ajoutée`;
    case "archived":
      return "Ticket archivé";
  }
}

const dateTime = new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "short" });
export const formatDateTime = (iso: string | null | undefined) =>
  iso ? dateTime.format(new Date(iso)) : "—";

export function formatLocation(location: {
  building?: string | null;
  floor?: string | null;
  room: string;
  details?: string | null;
}): string {
  return [location.building, location.floor, location.room].filter(Boolean).join(" · ");
}
