import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, call } from "../api/client";
import type { Site } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { ROLE_LABELS, can } from "../auth/permissions";
import { Card, Empty, ErrorAlert, Loading, Pagination } from "../components/ui";
import { describeEvent, formatDateTime } from "../lib/labels";
import { StatusBar, formatHours } from "./DashboardPage";

const LIMIT = 20;

export function SiteDetailPage() {
  const { siteId = "" } = useParams();
  const user = useCurrentUser();
  const site = useQuery({
    queryKey: ["site", siteId],
    queryFn: () => call(api.GET("/api/v1/sites/{site_id}", { params: { path: { site_id: siteId } } })),
  });
  const stats = useQuery({
    queryKey: ["dashboard", "site", siteId],
    queryFn: () =>
      call(api.GET("/api/v1/reports/sites/{site_id}", { params: { path: { site_id: siteId } } })),
  });

  if (site.isPending) return <Loading />;
  if (site.error) return <ErrorAlert error={site.error} />;
  const s = site.data;

  return (
    <div className="stack">
      <Link to="/sites" className="back-link">
        ← Établissements
      </Link>
      <div className="page-header">
        <div>
          <h1>
            {s.code} — {s.name}
          </h1>
          <p className="muted">
            {s.address}, {s.postal_code} {s.city} · Type {s.erp_type} · Catégorie {s.erp_category}
            {!s.is_active && " · Inactif"}
          </p>
        </div>
        <Link to={`/tickets?site=${s.id}`} className="btn">
          Voir les tickets
        </Link>
      </div>
      {stats.data && (
        <Card title="Indicateurs">
          <div className="kpis kpis-inline">
            <div className="kpi">
              <span className="kpi-value">{stats.data.open}</span>
              <span className="kpi-label">Ouverts</span>
            </div>
            <div className="kpi kpi-critical">
              <span className="kpi-value">{stats.data.open_by_priority.critical ?? 0}</span>
              <span className="kpi-label">Critiques</span>
            </div>
            <div className="kpi">
              <span className="kpi-value">{stats.data.total}</span>
              <span className="kpi-label">Total</span>
            </div>
            <div className="kpi">
              <span className="kpi-value">{formatHours(stats.data.avg_resolution_hours)}</span>
              <span className="kpi-label">Résolution moyenne</span>
            </div>
          </div>
          <StatusBar stats={stats.data} />
        </Card>
      )}
      {can.manage(user) && <SiteAdminCard site={s} />}
      {can.manage(user) && <MembersCard site={s} />}
      <SiteHistoryCard siteId={s.id} />
    </div>
  );
}

function SiteAdminCard({ site }: { site: Site }) {
  const queryClient = useQueryClient();
  const toggle = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/v1/sites/{site_id}", {
          params: { path: { site_id: site.id } },
          body: { is_active: !site.is_active },
        }),
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(["site", site.id], updated);
      void queryClient.invalidateQueries({ queryKey: ["sites"] });
    },
  });
  return (
    <Card title="Administration">
      <ErrorAlert error={toggle.error} />
      <p className="muted small">
        Un établissement inactif reste consultable mais n'accepte plus de nouveaux tickets.
      </p>
      <button className="btn" disabled={toggle.isPending} onClick={() => toggle.mutate()}>
        {site.is_active ? "Désactiver l'établissement" : "Réactiver l'établissement"}
      </button>
    </Card>
  );
}

function MembersCard({ site }: { site: Site }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState("");
  const members = useQuery({
    queryKey: ["users", "site", site.id],
    queryFn: () =>
      call(api.GET("/api/v1/users", { params: { query: { site_id: site.id, limit: 100 } } })),
  });
  const everyone = useQuery({
    queryKey: ["users", "all"],
    queryFn: () => call(api.GET("/api/v1/users", { params: { query: { limit: 100 } } })),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["users"] });
  const add = useMutation({
    mutationFn: (userId: string) =>
      call(
        api.POST("/api/v1/sites/{site_id}/members", {
          params: { path: { site_id: site.id } },
          body: { user_id: userId },
        }),
      ),
    onSuccess: () => {
      setSelected("");
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (userId: string) =>
      call(
        api.DELETE("/api/v1/sites/{site_id}/members/{user_id}", {
          params: { path: { site_id: site.id, user_id: userId } },
        }),
      ),
    onSuccess: refresh,
  });
  const memberIds = new Set(members.data?.items.map((m) => m.id));
  const candidates = (everyone.data?.items ?? []).filter(
    (u) => !memberIds.has(u.id) && u.is_active && u.role !== "admin",
  );

  return (
    <Card title="Membres de l'établissement">
      <ErrorAlert error={add.error ?? remove.error ?? members.error} />
      {members.data?.items.length === 0 && <Empty>Aucun membre.</Empty>}
      <ul className="list">
        {members.data?.items.map((member) => (
          <li key={member.id} className="list-row">
            <span>
              <strong>{member.full_name}</strong> <span className="muted small">{ROLE_LABELS[member.role]}</span>
            </span>
            <button className="btn btn-ghost btn-sm" disabled={remove.isPending} onClick={() => remove.mutate(member.id)}>
              Retirer
            </button>
          </li>
        ))}
      </ul>
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (selected) add.mutate(selected);
        }}
      >
        <select aria-label="Utilisateur à ajouter" value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">— Ajouter un utilisateur —</option>
          {candidates.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name} ({ROLE_LABELS[u.role]})
            </option>
          ))}
        </select>
        <button className="btn" disabled={!selected || add.isPending}>
          Ajouter
        </button>
      </form>
    </Card>
  );
}

function SiteHistoryCard({ siteId }: { siteId: string }) {
  const [offset, setOffset] = useState(0);
  const history = useQuery({
    queryKey: ["site-history", siteId, offset],
    queryFn: () =>
      call(
        api.GET("/api/v1/sites/{site_id}/history", {
          params: { path: { site_id: siteId }, query: { offset, limit: LIMIT } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  return (
    <Card title="Historique des interventions">
      <ErrorAlert error={history.error} />
      {history.data?.items.length === 0 && <Empty>Aucune intervention enregistrée.</Empty>}
      <ol className="timeline">
        {history.data?.items.map((event) => (
          <li key={event.id} className={`timeline-item event-${event.event_type}`}>
            <div className="timeline-title">
              <Link to={`/tickets/${event.ticket_id}`}>{describeEvent(event)}</Link>
            </div>
            <div className="muted small">
              {event.actor_name ?? "Système"} · {formatDateTime(event.created_at)}
            </div>
            {event.comment && <blockquote>{event.comment}</blockquote>}
          </li>
        ))}
      </ol>
      {history.data && (
        <Pagination offset={offset} limit={LIMIT} total={history.data.total} onChange={setOffset} />
      )}
    </Card>
  );
}
