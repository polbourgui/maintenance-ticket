import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError, api, call } from "../api/client";
import { useProviders } from "../api/queries";
import type { Provider } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { Card, Empty, ErrorAlert, Field, Loading } from "../components/ui";

const EMPTY = { company_name: "", contact_name: "", email: "", phone: "", specialty: "" };
const orNull = (value: string) => value.trim() || null;

export function ProvidersPage() {
  const user = useCurrentUser();
  const isAdmin = can.manage(user);
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const providers = useProviders(can.readProviders(user), !showInactive);

  if (!can.readProviders(user)) {
    return <ErrorAlert error={new ApiError(403, "Vous n'avez pas accès aux prestataires.")} />;
  }

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Prestataires externes</h1>
        {isAdmin && (
          <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Fermer" : "+ Nouveau prestataire"}
          </button>
        )}
      </div>
      {showForm && <ProviderForm onDone={() => setShowForm(false)} />}
      <label className="checkbox">
        <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
        Afficher aussi les prestataires inactifs
      </label>
      <ErrorAlert error={providers.error} />
      {providers.isPending ? (
        <Loading />
      ) : providers.data?.length === 0 ? (
        <Empty>Aucun prestataire.</Empty>
      ) : (
        <div className="cards-grid">
          {providers.data?.map((p) => <ProviderCard key={p.id} provider={p} isAdmin={isAdmin} />)}
        </div>
      )}
    </div>
  );
}

function ProviderCard({ provider, isAdmin }: { provider: Provider; isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const toggle = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/v1/providers/{provider_id}", {
          params: { path: { provider_id: provider.id } },
          body: { is_active: !provider.is_active },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["providers"] }),
  });
  return (
    <div className={`card ${provider.is_active ? "" : "inactive"}`}>
      <div className="site-name">{provider.company_name}</div>
      {provider.specialty && <span className="badge">{provider.specialty}</span>}
      <dl className="details compact">
        {provider.contact_name && (
          <>
            <dt>Contact</dt>
            <dd>{provider.contact_name}</dd>
          </>
        )}
        <dt>E-mail</dt>
        <dd>
          <a href={`mailto:${provider.email}`}>{provider.email}</a>
        </dd>
        {provider.phone && (
          <>
            <dt>Téléphone</dt>
            <dd>
              <a href={`tel:${provider.phone}`}>{provider.phone}</a>
            </dd>
          </>
        )}
      </dl>
      <ErrorAlert error={toggle.error} />
      {isAdmin && (
        <button className="btn btn-ghost btn-sm" disabled={toggle.isPending} onClick={() => toggle.mutate()}>
          {provider.is_active ? "Désactiver" : "Réactiver"}
        </button>
      )}
    </div>
  );
}

function ProviderForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY);
  const set = (key: keyof typeof EMPTY) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/providers", {
          body: {
            company_name: form.company_name.trim(),
            email: form.email.trim(),
            contact_name: orNull(form.contact_name),
            phone: orNull(form.phone),
            specialty: orNull(form.specialty),
          },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["providers"] });
      onDone();
    },
  });
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }
  return (
    <Card title="Nouveau prestataire">
      <form className="stack-sm" onSubmit={onSubmit}>
        <ErrorAlert error={create.error} />
        <div className="grid-2">
          <Field label="Raison sociale">
            <input required minLength={2} value={form.company_name} onChange={(e) => set("company_name")(e.target.value)} />
          </Field>
          <Field label="Spécialité">
            <input value={form.specialty} onChange={(e) => set("specialty")(e.target.value)} placeholder="SSI, ascenseurs, CVC…" />
          </Field>
          <Field label="E-mail (reçoit les assignations)">
            <input type="email" required value={form.email} onChange={(e) => set("email")(e.target.value)} />
          </Field>
          <Field label="Téléphone">
            <input type="tel" value={form.phone} onChange={(e) => set("phone")(e.target.value)} />
          </Field>
          <Field label="Nom du contact">
            <input value={form.contact_name} onChange={(e) => set("contact_name")(e.target.value)} />
          </Field>
        </div>
        <div className="form-actions">
          <button className="btn btn-primary" disabled={create.isPending}>
            Créer
          </button>
        </div>
      </form>
    </Card>
  );
}
