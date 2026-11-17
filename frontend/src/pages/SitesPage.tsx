import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, call } from "../api/client";
import { useSites } from "../api/queries";
import { useCurrentUser } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { Card, Empty, ErrorAlert, Field, Loading } from "../components/ui";

const EMPTY = { code: "", name: "", address: "", postal_code: "", city: "", erp_type: "", erp_category: "5" };

export function SitesPage() {
  const user = useCurrentUser();
  const sites = useSites();
  const [showForm, setShowForm] = useState(false);

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Établissements</h1>
        {can.manage(user) && (
          <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Fermer" : "+ Nouvel établissement"}
          </button>
        )}
      </div>
      {showForm && <SiteForm onDone={() => setShowForm(false)} />}
      <ErrorAlert error={sites.error} />
      {sites.isPending ? (
        <Loading />
      ) : sites.data?.length === 0 ? (
        <Empty>Aucun établissement accessible.</Empty>
      ) : (
        <div className="cards-grid">
          {sites.data?.map((site) => (
            <Link key={site.id} to={`/sites/${site.id}`} className={`card site-card ${site.is_active ? "" : "inactive"}`}>
              <div className="site-code">{site.code}</div>
              <div className="site-name">{site.name}</div>
              <div className="muted small">
                {site.address}, {site.postal_code} {site.city}
              </div>
              <div className="badges">
                <span className="badge">Type {site.erp_type}</span>
                <span className="badge">Catégorie {site.erp_category}</span>
                {!site.is_active && <span className="badge">Inactif</span>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function SiteForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY);
  const set = (key: keyof typeof EMPTY) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const create = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/sites", { body: { ...form, erp_category: Number(form.erp_category) } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sites"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setForm(EMPTY);
      onDone();
    },
  });
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }
  return (
    <Card title="Nouvel établissement">
      <form onSubmit={onSubmit} className="stack-sm">
        <ErrorAlert error={create.error} />
        <div className="grid-3">
          <Field label="Code" hint="Lettres, chiffres, - et _">
            <input required pattern="[A-Za-z0-9_\-]{2,32}" value={form.code} onChange={(e) => set("code")(e.target.value)} placeholder="ERP-PARIS-01" />
          </Field>
          <Field label="Nom">
            <input required minLength={2} value={form.name} onChange={(e) => set("name")(e.target.value)} />
          </Field>
          <Field label="Type ERP" hint="J, L, M, N, O, P, R, S, T, U, V, W, X, Y…">
            <input required pattern="[A-Za-z]{1,4}" value={form.erp_type} onChange={(e) => set("erp_type")(e.target.value)} />
          </Field>
        </div>
        <div className="grid-3">
          <Field label="Adresse">
            <input required minLength={2} value={form.address} onChange={(e) => set("address")(e.target.value)} />
          </Field>
          <Field label="Code postal">
            <input required pattern="[0-9A-Za-z \-]{3,10}" value={form.postal_code} onChange={(e) => set("postal_code")(e.target.value)} />
          </Field>
          <Field label="Ville">
            <input required value={form.city} onChange={(e) => set("city")(e.target.value)} />
          </Field>
        </div>
        <Field label="Catégorie ERP">
          <select value={form.erp_category} onChange={(e) => set("erp_category")(e.target.value)}>
            {[1, 2, 3, 4, 5].map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <div className="form-actions">
          <button className="btn btn-primary" disabled={create.isPending}>
            Créer
          </button>
        </div>
      </form>
    </Card>
  );
}
