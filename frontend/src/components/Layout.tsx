import { NavLink, Outlet } from "react-router-dom";

import { useAuth, useCurrentUser } from "../auth/AuthContext";
import { ROLE_LABELS, can } from "../auth/permissions";

export function Layout() {
  const user = useCurrentUser();
  const { logout } = useAuth();
  const links = [
    { to: "/tickets", label: "Tickets" },
    { to: "/dashboard", label: "Tableau de bord" },
    { to: "/sites", label: "Établissements" },
    ...(can.readProviders(user) ? [{ to: "/providers", label: "Prestataires" }] : []),
    ...(can.manage(user) ? [{ to: "/users", label: "Utilisateurs" }] : []),
  ];
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/tickets" className="brand">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span>Maintenance ERP</span>
        </NavLink>
        <nav className="nav" aria-label="Navigation principale">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="user-menu">
          <NavLink to="/account" className="user-link">
            <span className="user-name">{user.full_name}</span>
            <span className="user-role">{ROLE_LABELS[user.role]}</span>
          </NavLink>
          <button className="btn btn-ghost" onClick={() => void logout()}>
            Déconnexion
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
