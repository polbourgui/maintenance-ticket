import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { App } from "../App";
import { AuthProvider } from "../auth/AuthContext";

function renderApp(path = "/tickets") {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("login flow", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("redirects anonymous users to the login page and shows an error on bad credentials", async () => {
    const fetchMock = vi.fn((input: Request | string) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.includes("/auth/refresh")) return Promise.resolve(json(401, { detail: "no session" }));
      if (url.includes("/auth/login")) return Promise.resolve(json(401, { detail: "Invalid credentials" }));
      return Promise.resolve(json(404, {}));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp();

    expect(await screen.findByRole("button", { name: "Se connecter" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("E-mail"), "a@example.org");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou mot de passe incorrect.");
    expect(screen.getByLabelText("Mot de passe")).toHaveValue("");
  });

  it("restores an existing session from the refresh cookie", async () => {
    const me = {
      id: "u1", email: "admin@example.org", full_name: "Paula Admin", phone: null, role: "admin",
      is_active: true, site_ids: [], created_at: "2026-01-01T00:00:00Z", last_login_at: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: Request | string) => {
        const url = typeof input === "string" ? input : input.url;
        if (url.includes("/auth/refresh")) {
          return Promise.resolve(json(200, { access_token: "A", token_type: "bearer", expires_at: "", refresh_token: "r", refresh_expires_at: "" }));
        }
        if (url.includes("/users/me")) return Promise.resolve(json(200, me));
        return Promise.resolve(json(200, { items: [], total: 0, limit: 20, offset: 0 }));
      }),
    );
    renderApp();
    expect(await screen.findByText("Paula Admin")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Utilisateurs" })).toBeInTheDocument();
    expect(await screen.findByText("Aucun ticket ne correspond à ces critères.")).toBeInTheDocument();
  });
});
