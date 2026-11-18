import type { TicketEvent } from "../api/types";
import { describeEvent, formatLocation } from "./labels";

const event = (overrides: Partial<TicketEvent>): TicketEvent => ({
  id: "e1",
  ticket_id: "t1",
  actor_id: null,
  actor_name: null,
  event_type: "created",
  from_status: null,
  to_status: null,
  comment: null,
  details: {},
  created_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

describe("labels", () => {
  it("lists the edited fields once, in French", () => {
    const e = event({
      event_type: "updated",
      details: { fields: ["location_floor", "location_room", "priority"] },
    });
    expect(describeEvent(e)).toBe("Ticket modifié : localisation, priorité");
  });

  it("describes status changes", () => {
    expect(describeEvent(event({ event_type: "status_changed", from_status: "todo", to_status: "blocked" }))).toBe(
      "Statut : À faire → Bloqué",
    );
  });

  it("formats a location without empty parts", () => {
    expect(formatLocation({ building: null, floor: "RDC", room: "Hall" })).toBe("RDC · Hall");
  });
});
