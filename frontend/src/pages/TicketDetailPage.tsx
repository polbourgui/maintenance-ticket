import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, api, call, toApiError } from "../api/client";
import { useProviders, useSiteMap, useTechnicians } from "../api/queries";
import { authFetch } from "../api/session";
import type { PhotoKind, Ticket, TicketPhoto, TicketStatus, User } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { availableTransitions, can } from "../auth/permissions";
import { AuthImage } from "../components/AuthImage";
import { Card, Empty, ErrorAlert, Field, Loading, PriorityBadge, StatusBadge } from "../components/ui";
import {
  PHOTO_KIND_LABELS,
  STATUS_ACTIONS,
  describeEvent,
  formatDateTime,
  formatLocation,
} from "../lib/labels";

export function TicketDetailPage() {
  const { ticketId = "" } = useParams();
  const user = useCurrentUser();
  const siteMap = useSiteMap();
  const ticket = useQuery({
    queryKey: ["ticket", ticketId],
    queryFn: () =>
      call(api.GET("/api/v1/tickets/{ticket_id}", { params: { path: { ticket_id: ticketId } } })),
  });

  if (ticket.isPending) return <Loading />;
  if (ticket.error) {
    return (
      <>
        <ErrorAlert error={ticket.error} />
        <Link to="/tickets">← Retour aux tickets</Link>
      </>
    );
  }
  const t = ticket.data;
  const site = siteMap.get(t.site_id);

  return (
    <div className="stack">
      <Link to="/tickets" className="back-link">
        ← Tickets
      </Link>
      <div className="page-header">
        <div>
          <h1>{t.title}</h1>
          <div className="badges">
            <StatusBadge status={t.status} />
            <PriorityBadge priority={t.priority} />
            {t.archived_at && <span className="badge">Archivé le {formatDateTime(t.archived_at)}</span>}
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="stack">
          <Card title="Détails">
            <dl className="details">
              <dt>Établissement</dt>
              <dd>{site ? <Link to={`/sites/${site.id}`}>{site.code} — {site.name}</Link> : "—"}</dd>
              <dt>Localisation</dt>
              <dd>
                {formatLocation(t.location)}
                {t.location.details && <div className="muted small">{t.location.details}</div>}
              </dd>
              <dt>Créé par</dt>
              <dd>
                {t.created_by_name} · {formatDateTime(t.created_at)}
              </dd>
              <dt>Assigné à</dt>
              <dd>
                {t.assignee
                  ? `${t.assignee.display_name} (${t.assignee.type === "provider" ? "prestataire" : "technicien"})`
                  : "Personne"}
              </dd>
              <dt>Démarré</dt>
              <dd>{formatDateTime(t.started_at)}</dd>
              <dt>Terminé</dt>
              <dd>{formatDateTime(t.closed_at)}</dd>
            </dl>
            <p className="description">{t.description}</p>
          </Card>
          <PhotosCard ticket={t} user={user} />
          <HistoryCard ticketId={t.id} />
        </div>
        <aside className="stack">
          <StatusCard ticket={t} user={user} />
          {can.assign(user) && !t.archived_at && t.status !== "done" && <AssignmentCard ticket={t} />}
          {can.archive(user) && t.status === "done" && !t.archived_at && <ArchiveCard ticket={t} />}
        </aside>
      </div>
    </div>
  );
}

function useTicketUpdated(ticketId: string) {
  const queryClient = useQueryClient();
  return (updated?: Ticket) => {
    if (updated) queryClient.setQueryData(["ticket", ticketId], updated);
    void queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
    void queryClient.invalidateQueries({ queryKey: ["history", ticketId] });
    void queryClient.invalidateQueries({ queryKey: ["tickets"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
}

function StatusCard({ ticket, user }: { ticket: Ticket; user: User }) {
  const [comment, setComment] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const onUpdated = useTicketUpdated(ticket.id);
  const transitions = availableTransitions(user, ticket);
  const change = useMutation({
    mutationFn: (status: TicketStatus) =>
      call(
        api.POST("/api/v1/tickets/{ticket_id}/status", {
          params: { path: { ticket_id: ticket.id } },
          body: { status, comment: comment.trim() || null },
        }),
      ),
    onSuccess: (updated) => {
      setComment("");
      onUpdated(updated);
    },
  });

  function apply(status: TicketStatus) {
    setLocalError(null);
    if (status === "blocked" && !comment.trim()) {
      setLocalError("Indiquez le motif du blocage dans le commentaire.");
      return;
    }
    change.mutate(status);
  }

  if (transitions.length === 0) {
    const hint = ticket.archived_at
      ? "Ticket archivé : lecture seule."
      : user.role === "client"
        ? "Le suivi est assuré par l'équipe de maintenance."
        : ticket.status === "done"
          ? "Intervention terminée. Seul un administrateur peut rouvrir le ticket."
          : user.role === "technician"
            ? "Seul le technicien assigné peut faire évoluer ce ticket."
            : !ticket.assignee
              ? "Assignez le ticket pour pouvoir le démarrer."
              : null;
    return hint ? (
      <Card title="Statut">
        <p className="muted">{hint}</p>
      </Card>
    ) : null;
  }

  return (
    <Card title="Faire évoluer le statut">
      <ErrorAlert error={change.error} />
      {localError && <div className="alert alert-error">{localError}</div>}
      <Field label="Commentaire" hint="Obligatoire pour bloquer un ticket.">
        <textarea rows={3} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} />
      </Field>
      <div className="button-column">
        {transitions.map((status) => (
          <button
            key={status}
            className={`btn ${status === "done" ? "btn-success" : status === "blocked" ? "btn-warning" : "btn-primary"}`}
            disabled={change.isPending}
            onClick={() => apply(status)}
          >
            {ticket.status === "done" ? "Rouvrir" : STATUS_ACTIONS[status]}
          </button>
        ))}
      </div>
      {!ticket.assignee && ticket.status === "todo" && (
        <p className="muted small">Le ticket doit être assigné avant d'être démarré.</p>
      )}
    </Card>
  );
}

function AssignmentCard({ ticket }: { ticket: Ticket }) {
  const [type, setType] = useState<"technician" | "provider">(ticket.assignee?.type ?? "technician");
  const [selected, setSelected] = useState(ticket.assignee?.id ?? "");
  const technicians = useTechnicians(ticket.site_id, type === "technician");
  const providers = useProviders(type === "provider");
  const onUpdated = useTicketUpdated(ticket.id);
  const options = type === "technician" ? technicians : providers;

  const assign = useMutation({
    mutationFn: (body: { technician_id?: string; provider_id?: string }) =>
      call(
        api.PUT("/api/v1/tickets/{ticket_id}/assignment", {
          params: { path: { ticket_id: ticket.id } },
          body,
        }),
      ),
    onSuccess: onUpdated,
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    assign.mutate(type === "technician" ? { technician_id: selected } : { provider_id: selected });
  }

  return (
    <Card title="Assignation">
      <ErrorAlert error={assign.error} />
      <form onSubmit={onSubmit} className="stack-sm">
        <div className="segmented" role="radiogroup" aria-label="Type d'intervenant">
          {(["technician", "provider"] as const).map((value) => (
            <button
              type="button"
              key={value}
              role="radio"
              aria-checked={type === value}
              className={type === value ? "active" : ""}
              onClick={() => {
                setType(value);
                setSelected("");
              }}
            >
              {value === "technician" ? "Technicien" : "Prestataire"}
            </button>
          ))}
        </div>
        <select aria-label="Intervenant" value={selected} onChange={(e) => setSelected(e.target.value)} required>
          <option value="">— Choisir —</option>
          {(options.data ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {"full_name" in item ? item.full_name : `${item.company_name}${item.specialty ? ` (${item.specialty})` : ""}`}
            </option>
          ))}
        </select>
        {options.data?.length === 0 && (
          <p className="muted small">
            {type === "technician"
              ? "Aucun technicien actif rattaché à cet établissement."
              : "Aucun prestataire actif."}
          </p>
        )}
        <button className="btn btn-primary" disabled={!selected || assign.isPending}>
          Assigner et notifier
        </button>
        {ticket.assignee && ticket.status !== "in_progress" && (
          <button type="button" className="btn btn-ghost" disabled={assign.isPending} onClick={() => assign.mutate({})}>
            Retirer l'assignation
          </button>
        )}
      </form>
    </Card>
  );
}

function ArchiveCard({ ticket }: { ticket: Ticket }) {
  const onUpdated = useTicketUpdated(ticket.id);
  const archive = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/tickets/{ticket_id}/archive", { params: { path: { ticket_id: ticket.id } } })),
    onSuccess: onUpdated,
  });
  return (
    <Card title="Archivage">
      <ErrorAlert error={archive.error} />
      <p className="muted small">Le ticket deviendra en lecture seule. Il reste consultable dans l'historique.</p>
      <button
        className="btn"
        disabled={archive.isPending}
        onClick={() => window.confirm("Archiver ce ticket ?") && archive.mutate()}
      >
        Archiver le ticket
      </button>
    </Card>
  );
}

function PhotosCard({ ticket, user }: { ticket: Ticket; user: User }) {
  const queryClient = useQueryClient();
  const photos = useQuery({
    queryKey: ["photos", ticket.id],
    queryFn: () =>
      call(api.GET("/api/v1/tickets/{ticket_id}/photos", { params: { path: { ticket_id: ticket.id } } })),
  });
  const upload = useMutation({
    mutationFn: async ({ kind, file }: { kind: PhotoKind; file: File }) => {
      const form = new FormData();
      form.append("kind", kind);
      form.append("file", file);
      const response = await authFetch(`/api/v1/tickets/${ticket.id}/photos`, { method: "POST", body: form });
      if (!response.ok) throw toApiError(response.status, await response.json().catch(() => null));
      return (await response.json()) as TicketPhoto;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["photos", ticket.id] });
      void queryClient.invalidateQueries({ queryKey: ["history", ticket.id] });
    },
  });
  const canUpload = can.uploadPhoto(user) && !ticket.archived_at;

  return (
    <Card title="Photos de l'intervention">
      <ErrorAlert error={upload.error} />
      {photos.isPending && <Loading />}
      <div className="photo-columns">
        {(["before", "after"] as const).map((kind) => {
          const list = (photos.data ?? []).filter((p) => p.kind === kind);
          return (
            <div key={kind}>
              <h3>{PHOTO_KIND_LABELS[kind]}</h3>
              {list.length === 0 && <Empty>Aucune photo.</Empty>}
              <div className="photo-grid">
                {list.map((photo) => (
                  <figure key={photo.id} className="photo" title={formatDateTime(photo.created_at)}>
                    <AuthImage
                      src={`/api/v1/tickets/${ticket.id}/photos/${photo.id}`}
                      alt={`Photo ${PHOTO_KIND_LABELS[kind].toLowerCase()} du ${formatDateTime(photo.created_at)}`}
                    />
                  </figure>
                ))}
              </div>
              {canUpload && (
                <PhotoInput
                  label={`Ajouter une photo « ${PHOTO_KIND_LABELS[kind].toLowerCase()} »`}
                  disabled={upload.isPending}
                  onFile={(file) => upload.mutate({ kind, file })}
                />
              )}
            </div>
          );
        })}
      </div>
      {upload.isPending && <p className="muted small">Envoi en cours…</p>}
    </Card>
  );
}

function PhotoInput({ label, disabled, onFile }: { label: string; disabled: boolean; onFile: (file: File) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <label className={`btn btn-ghost upload ${disabled ? "disabled" : ""}`}>
      {label}
      <input
        ref={ref}
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        disabled={disabled}
        className="visually-hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          if (ref.current) ref.current.value = "";
        }}
      />
    </label>
  );
}

function HistoryCard({ ticketId }: { ticketId: string }) {
  const history = useQuery({
    queryKey: ["history", ticketId],
    queryFn: () =>
      call(api.GET("/api/v1/tickets/{ticket_id}/history", { params: { path: { ticket_id: ticketId } } })),
  });
  if (history.error instanceof ApiError && history.error.status === 403) return null;
  return (
    <Card title="Historique">
      <ErrorAlert error={history.error} />
      {history.isPending && <Loading />}
      <ol className="timeline">
        {(history.data ?? []).map((event) => (
          <li key={event.id} className={`timeline-item event-${event.event_type}`}>
            <div className="timeline-title">{describeEvent(event)}</div>
            <div className="muted small">
              {event.actor_name ?? "Système"} · {formatDateTime(event.created_at)}
            </div>
            {event.comment && <blockquote>{event.comment}</blockquote>}
          </li>
        ))}
      </ol>
    </Card>
  );
}
