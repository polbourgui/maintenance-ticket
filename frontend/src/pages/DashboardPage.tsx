import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api, call } from "../api/client";
import type { SiteStats } from "../api/types";
import { Card, Empty, ErrorAlert, Loading } from "../components/ui";
import { STATUSES, STATUS_LABELS, formatDateTime } from "../lib/labels";

export function DashboardPage() {
  const report = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => call(api.GET("/api/v1/reports/dashboard")),
  });
  if (report.isPending) return <Loading />;
  if (report.error) return <ErrorAlert error={report.error} />;
  const { totals, sites, generated_at } = report.data;
  const criticalOpen = sites.reduce((sum, s) => sum + (s.open_by_priority.critical ?? 0), 0);

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Tableau de bord</h1>
        <span className="muted small">Mis à jour le {formatDateTime(generated_at)}</span>
      </div>
      <div className="kpis">
        {STATUSES.map((status) => (
          <Link key={status} to={`/tickets?status=${status}`} className={`kpi kpi-${status}`}>
            <span className="kpi-value">{totals[status] ?? 0}</span>
            <span className="kpi-label">{STATUS_LABELS[status]}</span>
          </Link>
        ))}
        <Link to="/tickets?priority=critical" className="kpi kpi-critical">
          <span className="kpi-value">{criticalOpen}</span>
          <span className="kpi-label">Critiques ouverts</span>
        </Link>
      </div>
      <Card title="Par établissement">
        {sites.length === 0 ? (
          <Empty>Aucun établissement.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Établissement</th>
                  <th>Répartition</th>
                  <th className="num">Ouverts</th>
                  <th className="num">Critiques</th>
                  <th className="num">Bloqués</th>
                  <th className="num">Total</th>
                  <th className="num">Archivés</th>
                  <th className="num">Résolution moy.</th>
                </tr>
              </thead>
              <tbody>
                {sites.map((site) => (
                  <tr key={site.site_id}>
                    <td>
                      <Link to={`/sites/${site.site_id}`}>
                        <strong>{site.site_code}</strong> {site.site_name}
                      </Link>
                    </td>
                    <td>
                      <StatusBar stats={site} />
                    </td>
                    <td className="num">{site.open}</td>
                    <td className="num">{site.open_by_priority.critical || "—"}</td>
                    <td className="num">{site.by_status.blocked || "—"}</td>
                    <td className="num">{site.total}</td>
                    <td className="num">{site.archived}</td>
                    <td className="num">{formatHours(site.avg_resolution_hours)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

export function StatusBar({ stats }: { stats: SiteStats }) {
  if (stats.total === 0) return <span className="muted small">Aucun ticket</span>;
  return (
    <div
      className="status-bar"
      role="img"
      aria-label={STATUSES.map((s) => `${STATUS_LABELS[s]} : ${stats.by_status[s] ?? 0}`).join(", ")}
    >
      {STATUSES.map((status) => {
        const count = stats.by_status[status] ?? 0;
        return count ? (
          <span
            key={status}
            className={`seg seg-${status}`}
            style={{ flexGrow: count }}
            title={`${STATUS_LABELS[status]} : ${count}`}
          />
        ) : null;
      })}
    </div>
  );
}

export function formatHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "—";
  if (hours < 48) return `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} j`;
}
