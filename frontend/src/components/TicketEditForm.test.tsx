import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Ticket } from "../api/types";
import { TicketEditForm } from "./TicketEditForm";

const ticket: Ticket = {
  id: "t1",
  site_id: "s1",
  title: "Fuite",
  description: "Fuite sous l'évier",
  priority: "medium",
  status: "todo",
  location: { building: "Bât. A", floor: null, room: "Cuisine", details: null },
  created_by_id: "c1",
  created_by_name: "Client",
  assignee: null,
  started_at: null,
  closed_at: null,
  archived_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("TicketEditForm", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("pre-fills the form and sends the full update", async () => {
    const sent: unknown[] = [];
    const fetchMock = vi.fn(async (request: Request) => {
      const body = await request.json();
      sent.push(body);
      return new Response(JSON.stringify({ ...ticket, ...body }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const onSaved = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <TicketEditForm ticket={ticket} onSaved={onSaved} onCancel={() => {}} />
      </QueryClientProvider>,
    );

    expect(screen.getByLabelText("Titre")).toHaveValue("Fuite");
    expect(screen.getByLabelText("Bâtiment")).toHaveValue("Bât. A");
    await userEvent.selectOptions(screen.getByLabelText("Priorité"), "critical");
    await userEvent.type(screen.getByLabelText("Étage"), "R+1");
    await userEvent.clear(screen.getByLabelText("Bâtiment"));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await vi.waitFor(() => expect(onSaved).toHaveBeenCalled());
    const request = fetchMock.mock.calls[0]![0];
    expect(request.method).toBe("PATCH");
    expect(new URL(request.url).pathname).toBe("/api/v1/tickets/t1");
    expect(sent[0]).toEqual({
      title: "Fuite",
      description: "Fuite sous l'évier",
      priority: "critical",
      location: { building: null, floor: "R+1", room: "Cuisine", details: null },
    });
  });
});
