import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";

import { api, call } from "../api/client";
import type { Ticket, TicketPriority } from "../api/types";
import { PRIORITIES, PRIORITY_LABELS } from "../lib/labels";
import { ErrorAlert, Field } from "./ui";

const blankToNull = (value: string) => (value.trim() ? value.trim() : null);

export function TicketEditForm({
  ticket,
  onSaved,
  onCancel,
}: {
  ticket: Ticket;
  onSaved: (ticket: Ticket) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    title: ticket.title,
    description: ticket.description,
    priority: ticket.priority,
    building: ticket.location.building ?? "",
    floor: ticket.location.floor ?? "",
    room: ticket.location.room,
    details: ticket.location.details ?? "",
  });
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/v1/tickets/{ticket_id}", {
          params: { path: { ticket_id: ticket.id } },
          body: {
            title: form.title.trim(),
            description: form.description.trim(),
            priority: form.priority,
            location: {
              building: blankToNull(form.building),
              floor: blankToNull(form.floor),
              room: form.room.trim(),
              details: blankToNull(form.details),
            },
          },
        }),
      ),
    onSuccess: onSaved,
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <form className="stack-sm" onSubmit={onSubmit} aria-label="Modifier le ticket">
      <ErrorAlert error={save.error} />
      <Field label="Titre">
        <input required minLength={3} maxLength={200} value={form.title} onChange={(e) => set("title")(e.target.value)} />
      </Field>
      <Field label="Description">
        <textarea required maxLength={10000} rows={5} value={form.description} onChange={(e) => set("description")(e.target.value)} />
      </Field>
      <Field label="Priorité">
        <select value={form.priority} onChange={(e) => set("priority")(e.target.value as TicketPriority)}>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABELS[p]}
            </option>
          ))}
        </select>
      </Field>
      <div className="grid-3">
        <Field label="Bâtiment">
          <input maxLength={120} value={form.building} onChange={(e) => set("building")(e.target.value)} />
        </Field>
        <Field label="Étage">
          <input maxLength={32} value={form.floor} onChange={(e) => set("floor")(e.target.value)} />
        </Field>
        <Field label="Local / pièce">
          <input required maxLength={120} value={form.room} onChange={(e) => set("room")(e.target.value)} />
        </Field>
      </div>
      <Field label="Précisions">
        <input maxLength={500} value={form.details} onChange={(e) => set("details")(e.target.value)} />
      </Field>
      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Annuler
        </button>
        <button className="btn btn-primary" disabled={save.isPending}>
          {save.isPending ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </form>
  );
}
