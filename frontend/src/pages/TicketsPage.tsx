import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { api, call } from "../api/client";
import { useSiteMap } from "../api/queries";
import type { TicketPriority, TicketStatus } from "../api/types";
import { Empty, ErrorAlert, Loading, Pagination, PriorityBadge, StatusBadge } from "../components/ui";
import {
  PRIORITIES,
  PRIORITY_LABELS,
  STATUSES,
  STATUS_LABELS,
  formatDateTime,
  formatLocation,
} from "../lib/labels";

const LIMIT = 20;

export function TicketsPage() {
  const [params, setParams] = useSearchParams();
  const siteMap = useSiteMap();
  const filters = {
    site_id: params.get("site") || undefined,
    status: (params.get("status") || undefined) as TicketStatus | undefined,
    priority: (params.get("priority") || undefined) as TicketPriority | undefined,
    include_archived: params.get("archived") === "1",
    offset: Number(params.get("offset") ?? 0) || 0,
  };

  const tickets = useQuery({
    queryKey: ["tickets", filters],
    queryFn: () =>
      call(api.GET("/api/v1/tickets", { params: { query: { ...filters, limit: LIMIT } } })),
    placeholderData: keepPreviousData,
  });

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "offset") next.delete("offset");
    setParams(next, { replace: true });
  }

  return (
    <>
      <div className="page-header">
        <h1>Tickets</h1>
        <Link to="/tickets/new" className="btn btn-primary">
          + Nouveau ticket
        </Link>
      </div>

      <div className="filters card">
        <select aria-label="Établissement" value={filters.site_id ?? ""} onChange={(e) => update("site", e.target.value)}>
          <option value="">Tous les établissements</option>
          {[...siteMap.values()].map((site) => (
            <option key={site.id} value={site.id}>
              {site.code} — {site.name}
            </option>
          ))}
        </select>
        <select aria-label="Statut" value={filters.status ?? ""} onChange={(e) => update("status", e.target.value)}>
          <option value="">Tous les statuts</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
        <select aria-label="Priorité" value={filters.priority ?? ""} onChange={(e) => update("priority", e.target.value)}>
          <option value="">Toutes priorités</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABELS[p]}
            </option>
          ))}
        </select>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={filters.include_archived}
            onChange={(e) => update("archived", e.target.checked ? "1" : "")}
          />
          Inclure les archivés
        </label>
      </div>

      <ErrorAlert error={tickets.error} />
      {tickets.isPending ? (
        <Loading />
      ) : tickets.data && tickets.data.items.length === 0 ? (
        <Empty>Aucun ticket ne correspond à ces critères.</Empty>
      ) : (
        <ul className="ticket-list">
          {tickets.data?.items.map((ticket) => {
            const site = siteMap.get(ticket.site_id);
            return (
              <li key={ticket.id}>
                <Link to={`/tickets/${ticket.id}`} className="ticket-row">
                  <div className="ticket-main">
                    <span className="ticket-title">{ticket.title}</span>
                    <span className="muted small">
                      {site ? `${site.code} · ` : ""}
                      {formatLocation(ticket.location)}
                    </span>
                  </div>
                  <div className="ticket-meta">
                    <PriorityBadge priority={ticket.priority} />
                    <StatusBadge status={ticket.status} />
                    {ticket.archived_at && <span className="badge">Archivé</span>}
                  </div>
                  <div className="ticket-side muted small">
                    <span>{ticket.assignee?.display_name ?? "Non assigné"}</span>
                    <span>{formatDateTime(ticket.created_at)}</span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {tickets.data && (
        <Pagination
          offset={filters.offset}
          limit={LIMIT}
          total={tickets.data.total}
          onChange={(offset) => update("offset", String(offset))}
        />
      )}
    </>
  );
}
