import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api, call } from "../api/client";
import { useSites } from "../api/queries";
import type { TicketPriority } from "../api/types";
import { Card, ErrorAlert, Field, Loading } from "../components/ui";
import { PRIORITIES, PRIORITY_LABELS } from "../lib/labels";

const blankToNull = (value: string) => (value.trim() ? value.trim() : null);

export function TicketNewPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const sites = useSites();
  const activeSites = (sites.data ?? []).filter((site) => site.is_active);
  const [form, setForm] = useState({
    site_id: "",
    title: "",
    description: "",
    priority: "medium" as TicketPriority,
    building: "",
    floor: "",
    room: "",
    details: "",
  });
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/tickets", {
          body: {
            site_id: form.site_id || (activeSites[0]?.id ?? ""),
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
    onSuccess: (ticket) => {
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      navigate(`/tickets/${ticket.id}`);
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  if (sites.isPending) return <Loading />;
  if (activeSites.length === 0) {
    return (
      <Card title="Nouveau ticket">
        <p className="muted">Vous n'êtes rattaché à aucun établissement actif.</p>
      </Card>
    );
  }

  return (
    <form onSubmit={onSubmit} className="stack">
      <div className="page-header">
        <h1>Nouveau ticket</h1>
      </div>
      <ErrorAlert error={create.error} />
      <Card title="Intervention">
        <div className="grid-2">
          <Field label="Établissement">
            <select required value={form.site_id || activeSites[0]?.id} onChange={(e) => set("site_id")(e.target.value)}>
              {activeSites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.code} — {site.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Priorité">
            <select value={form.priority} onChange={(e) => set("priority")(e.target.value)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABELS[p]}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Titre">
          <input required minLength={3} maxLength={200} value={form.title} onChange={(e) => set("title")(e.target.value)} placeholder="Ex. Alarme incendie en défaut zone 3" />
        </Field>
        <Field label="Description">
          <textarea required maxLength={10000} rows={5} value={form.description} onChange={(e) => set("description")(e.target.value)} />
        </Field>
      </Card>
      <Card title="Localisation précise">
        <div className="grid-3">
          <Field label="Bâtiment">
            <input maxLength={120} value={form.building} onChange={(e) => set("building")(e.target.value)} placeholder="Bâtiment A" />
          </Field>
          <Field label="Étage">
            <input maxLength={32} value={form.floor} onChange={(e) => set("floor")(e.target.value)} placeholder="R+1" />
          </Field>
          <Field label="Local / pièce">
            <input required maxLength={120} value={form.room} onChange={(e) => set("room")(e.target.value)} placeholder="Local technique" />
          </Field>
        </div>
        <Field label="Précisions">
          <input maxLength={500} value={form.details} onChange={(e) => set("details")(e.target.value)} placeholder="Trappe au plafond, à gauche de l'entrée…" />
        </Field>
      </Card>
      <div className="form-actions">
        <button type="button" className="btn" onClick={() => navigate(-1)}>
          Annuler
        </button>
        <button className="btn btn-primary" disabled={create.isPending}>
          {create.isPending ? "Création…" : "Créer le ticket"}
        </button>
      </div>
    </form>
  );
}
