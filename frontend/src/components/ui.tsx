import { cloneElement, useId } from "react";
import type { ReactElement, ReactNode } from "react";

import type { TicketPriority, TicketStatus } from "../api/types";
import { errorMessage } from "../api/client";
import { PRIORITY_LABELS, STATUS_LABELS } from "../lib/labels";

export function StatusBadge({ status }: { status: TicketStatus }) {
  return <span className={`badge status-${status}`}>{STATUS_LABELS[status]}</span>;
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  return <span className={`badge priority-${priority}`}>{PRIORITY_LABELS[priority]}</span>;
}

export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="alert alert-error" role="alert">
      {errorMessage(error)}
    </div>
  );
}

export function SuccessAlert({ children }: { children: ReactNode }) {
  return (
    <div className="alert alert-success" role="status">
      {children}
    </div>
  );
}

export function Loading({ label = "Chargement…" }: { label?: string }) {
  return (
    <p className="muted" aria-busy="true">
      {label}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Card({
  title,
  actions,
  children,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-header">
          {title && <h2>{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactElement<{ id?: string; "aria-describedby"?: string }>;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {cloneElement(children, { id, "aria-describedby": hint ? hintId : undefined })}
      {hint && (
        <span className="field-hint" id={hintId}>
          {hint}
        </span>
      )}
    </div>
  );
}

export function Pagination({
  offset,
  limit,
  total,
  onChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        className="btn"
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        ← Précédent
      </button>
      <span>
        Page {page} / {pages}
      </span>
      <button className="btn" disabled={page >= pages} onClick={() => onChange(offset + limit)}>
        Suivant →
      </button>
    </nav>
  );
}
