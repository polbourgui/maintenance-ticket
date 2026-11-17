import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { AccountPage } from "./pages/AccountPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ProvidersPage } from "./pages/ProvidersPage";
import { SiteDetailPage } from "./pages/SiteDetailPage";
import { SitesPage } from "./pages/SitesPage";
import { TicketDetailPage } from "./pages/TicketDetailPage";
import { TicketNewPage } from "./pages/TicketNewPage";
import { TicketsPage } from "./pages/TicketsPage";
import { UsersPage } from "./pages/UsersPage";

export function App() {
  const { state } = useAuth();
  const location = useLocation();

  if (state.status === "loading") {
    return (
      <div className="centered">
        <Loading label="Ouverture de la session…" />
      </div>
    );
  }
  if (state.status === "anonymous") {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace state={{ from: location }} />} />
      </Routes>
    );
  }
  const isAdmin = state.user.role === "admin";
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/tickets" replace />} />
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/tickets/new" element={<TicketNewPage />} />
        <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/sites" element={<SitesPage />} />
        <Route path="/sites/:siteId" element={<SiteDetailPage />} />
        <Route path="/providers" element={<ProvidersPage />} />
        {isAdmin && <Route path="/users" element={<UsersPage />} />}
        <Route path="/account" element={<AccountPage />} />
        <Route path="/login" element={<Navigate to="/tickets" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

function NotFound() {
  return (
    <div className="card">
      <h1>Page introuvable</h1>
      <p className="muted">Cette page n'existe pas ou vous n'y avez pas accès.</p>
    </div>
  );
}
