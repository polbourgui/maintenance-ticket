import type { Ticket, User } from "../api/types";
import { availableTransitions, can } from "./permissions";

const user = (role: User["role"], id = "u1"): User => ({
  id,
  email: `${id}@example.org`,
  full_name: id,
  phone: null,
  role,
  is_active: true,
  site_ids: ["s1"],
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
});

const ticket = (overrides: Partial<Ticket> = {}): Ticket => ({
  id: "t1",
  site_id: "s1",
  title: "Fuite",
  description: "d",
  priority: "high",
  status: "todo",
  location: { building: null, floor: null, room: "R1", details: null },
  created_by_id: "c1",
  created_by_name: "Client",
  assignee: { type: "technician", id: "tech", display_name: "Tech" },
  started_at: null,
  closed_at: null,
  archived_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

describe("permissions (UI mirror of the RBAC matrix)", () => {
  it("only the assigned technician or an admin can change status", () => {
    expect(can.changeStatus(user("technician", "tech"), ticket())).toBe(true);
    expect(can.changeStatus(user("technician", "other"), ticket())).toBe(false);
    expect(can.changeStatus(user("client"), ticket())).toBe(false);
    expect(can.changeStatus(user("admin"), ticket())).toBe(true);
  });

  it("offers workflow transitions", () => {
    const tech = user("technician", "tech");
    expect(availableTransitions(tech, ticket())).toEqual(["in_progress", "blocked"]);
    expect(availableTransitions(tech, ticket({ status: "in_progress" }))).toEqual(["todo", "blocked", "done"]);
    expect(availableTransitions(tech, ticket({ status: "blocked" }))).toEqual(["todo", "in_progress"]);
  });

  it("requires an assignee to start", () => {
    expect(availableTransitions(user("admin"), ticket({ assignee: null }))).toEqual(["blocked"]);
  });

  it("only admins reopen; archived tickets are read-only", () => {
    expect(availableTransitions(user("technician", "tech"), ticket({ status: "done" }))).toEqual([]);
    expect(availableTransitions(user("admin"), ticket({ status: "done" }))).toEqual(["in_progress"]);
    expect(availableTransitions(user("admin"), ticket({ archived_at: "2026-01-02T00:00:00Z" }))).toEqual([]);
  });

  it("restricts management to admins and providers to staff", () => {
    expect(can.manage(user("admin"))).toBe(true);
    expect(can.manage(user("technician"))).toBe(false);
    expect(can.readProviders(user("technician"))).toBe(true);
    expect(can.readProviders(user("client"))).toBe(false);
  });
});
