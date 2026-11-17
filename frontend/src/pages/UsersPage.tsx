import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";

import { api, call } from "../api/client";
import { useSites } from "../api/queries";
import type { Role, User } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { ROLE_LABELS } from "../auth/permissions";
import { Card, ErrorAlert, Field, Loading, Pagination } from "../components/ui";
import { formatDateTime } from "../lib/labels";

const ROLES = Object.keys(ROLE_LABELS) as Role[];
const LIMIT = 50;

export function UsersPage() {
  const [role, setRole] = useState<Role | "">("");
  const [offset, setOffset] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const users = useQuery({
    queryKey: ["users", "list", role, offset],
    queryFn: () =>
      call(api.GET("/api/v1/users", { params: { query: { role: role || undefined, offset, limit: LIMIT } } })),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Utilisateurs</h1>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Fermer" : "+ Nouvel utilisateur"}
        </button>
      </div>
      {showForm && <UserCreateForm onDone={() => setShowForm(false)} />}
      <div className="filters card">
        <select aria-label="Rôle" value={role} onChange={(e) => { setRole(e.target.value as Role | ""); setOffset(0); }}>
          <option value="">Tous les rôles</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </select>
      </div>
      <ErrorAlert error={users.error} />
      {users.isPending ? (
        <Loading />
      ) : (
        <Card>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Nom</th>
                  <th>E-mail</th>
                  <th>Rôle</th>
                  <th className="num">Sites</th>
                  <th>Dernière connexion</th>
                  <th>État</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.data?.items.map((u) =>
                  editing === u.id ? (
                    <tr key={u.id}>
                      <td colSpan={7}>
                        <UserEditForm user={u} onDone={() => setEditing(null)} />
                      </td>
                    </tr>
                  ) : (
                    <tr key={u.id} className={u.is_active ? "" : "row-inactive"}>
                      <td>{u.full_name}</td>
                      <td className="small">{u.email}</td>
                      <td>{ROLE_LABELS[u.role]}</td>
                      <td className="num">{u.role === "admin" ? "Tous" : u.site_ids.length}</td>
                      <td className="small">{formatDateTime(u.last_login_at)}</td>
                      <td>{u.is_active ? "Actif" : "Inactif"}</td>
                      <td className="num">
                        {!u.email.endsWith(".invalid") && (
                          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(u.id)}>
                            Modifier
                          </button>
                        )}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
          {users.data && <Pagination offset={offset} limit={LIMIT} total={users.data.total} onChange={setOffset} />}
        </Card>
      )}
    </div>
  );
}

function SiteCheckboxes({ value, onChange }: { value: string[]; onChange: (ids: string[]) => void }) {
  const sites = useSites();
  return (
    <fieldset className="checkbox-group">
      <legend className="field-label">Établissements</legend>
      {sites.data?.map((site) => (
        <label key={site.id} className="checkbox">
          <input
            type="checkbox"
            checked={value.includes(site.id)}
            onChange={(e) =>
              onChange(e.target.checked ? [...value, site.id] : value.filter((id) => id !== site.id))
            }
          />
          {site.code} — {site.name}
        </label>
      ))}
    </fieldset>
  );
}

function UserCreateForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ email: "", full_name: "", phone: "", password: "", role: "technician" as Role });
  const [siteIds, setSiteIds] = useState<string[]>([]);
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/v1/users", {
          body: { ...form, phone: form.phone.trim() || null, site_ids: form.role === "admin" ? [] : siteIds },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      onDone();
    },
  });
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }
  return (
    <Card title="Nouvel utilisateur">
      <form onSubmit={onSubmit} className="stack-sm">
        <ErrorAlert error={create.error} />
        <div className="grid-2">
          <Field label="Nom complet">
            <input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </Field>
          <Field label="E-mail">
            <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <Field label="Téléphone (optionnel)">
            <input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Field>
          <Field label="Rôle">
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Mot de passe initial"
            hint="12 caractères min., 3 types parmi minuscules, majuscules, chiffres, symboles. À transmettre de façon sécurisée."
          >
            <input type="password" autoComplete="new-password" required minLength={12} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </Field>
        </div>
        {form.role === "admin" ? (
          <p className="muted small">Les administrateurs ont accès à tous les établissements.</p>
        ) : (
          <SiteCheckboxes value={siteIds} onChange={setSiteIds} />
        )}
        <div className="form-actions">
          <button className="btn btn-primary" disabled={create.isPending}>
            Créer l'utilisateur
          </button>
        </div>
      </form>
    </Card>
  );
}

function UserEditForm({ user, onDone }: { user: User; onDone: () => void }) {
  const me = useCurrentUser();
  const queryClient = useQueryClient();
  const [role, setRole] = useState<Role>(user.role);
  const [active, setActive] = useState(user.is_active);
  const [siteIds, setSiteIds] = useState<string[]>(user.site_ids);
  const isMe = me.id === user.id;
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["users"] });
    onDone();
  };
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/v1/users/{user_id}", {
          params: { path: { user_id: user.id } },
          body: isMe ? { site_ids: siteIds } : { role, is_active: active, site_ids: siteIds },
        }),
      ),
    onSuccess: refresh,
  });
  const anonymize = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/users/{user_id}/anonymize", { params: { path: { user_id: user.id } } })),
    onSuccess: refresh,
  });

  return (
    <div className="stack-sm edit-panel">
      <strong>
        {user.full_name} <span className="muted small">{user.email}</span>
      </strong>
      <ErrorAlert error={save.error ?? anonymize.error} />
      <div className="grid-2">
        <Field label="Rôle">
          <select value={role} disabled={isMe} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </Field>
        <label className="checkbox">
          <input type="checkbox" checked={active} disabled={isMe} onChange={(e) => setActive(e.target.checked)} />
          Compte actif
        </label>
      </div>
      {role !== "admin" && <SiteCheckboxes value={siteIds} onChange={setSiteIds} />}
      <p className="muted small">Changer le rôle ou désactiver le compte ferme immédiatement ses sessions.</p>
      <div className="form-actions">
        {!isMe && (
          <button
            className="btn btn-danger"
            disabled={anonymize.isPending}
            onClick={() =>
              window.confirm(
                `Anonymiser définitivement ${user.full_name} ? (droit à l'effacement RGPD — irréversible)`,
              ) && anonymize.mutate()
            }
          >
            Anonymiser (RGPD)
          </button>
        )}
        <span className="spacer" />
        <button className="btn" onClick={onDone}>
          Annuler
        </button>
        <button className="btn btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>
          Enregistrer
        </button>
      </div>
    </div>
  );
}
