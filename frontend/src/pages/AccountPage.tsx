import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";

import { api, call } from "../api/client";
import { setAccessToken } from "../api/session";
import { useCurrentUser } from "../auth/AuthContext";
import { ROLE_LABELS } from "../auth/permissions";
import { Card, ErrorAlert, Field, SuccessAlert } from "../components/ui";
import { formatDateTime } from "../lib/labels";

export function AccountPage() {
  const user = useCurrentUser();
  return (
    <div className="stack">
      <div className="page-header">
        <h1>Mon compte</h1>
      </div>
      <Card title="Profil">
        <dl className="details">
          <dt>Nom</dt>
          <dd>{user.full_name}</dd>
          <dt>E-mail</dt>
          <dd>{user.email}</dd>
          <dt>Téléphone</dt>
          <dd>{user.phone ?? "—"}</dd>
          <dt>Rôle</dt>
          <dd>{ROLE_LABELS[user.role]}</dd>
          <dt>Compte créé le</dt>
          <dd>{formatDateTime(user.created_at)}</dd>
        </dl>
        <p className="muted small">Pour corriger ces informations, contactez un administrateur.</p>
      </Card>
      <PasswordCard />
      <SessionsCard />
      <PrivacyCard />
    </div>
  );
}

function PasswordCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const change = useMutation({
    mutationFn: () =>
      call(api.POST("/api/v1/auth/password", { body: { current_password: current, new_password: next } })),
    // Every session is revoked server-side: back to the login screen.
    onSuccess: () => setAccessToken(null),
  });
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setMismatch(next !== confirm);
    if (next === confirm) change.mutate();
  }
  return (
    <Card title="Mot de passe">
      <form className="stack-sm" onSubmit={onSubmit}>
        <ErrorAlert error={change.error} />
        {mismatch && <div className="alert alert-error">Les deux mots de passe ne correspondent pas.</div>}
        <div className="grid-3">
          <Field label="Mot de passe actuel">
            <input type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </Field>
          <Field label="Nouveau mot de passe" hint="12 caractères min., 3 types de caractères.">
            <input type="password" autoComplete="new-password" required minLength={12} value={next} onChange={(e) => setNext(e.target.value)} />
          </Field>
          <Field label="Confirmation">
            <input type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </Field>
        </div>
        <p className="muted small">Toutes vos sessions seront fermées : vous devrez vous reconnecter.</p>
        <div className="form-actions">
          <button className="btn btn-primary" disabled={change.isPending}>
            Changer le mot de passe
          </button>
        </div>
      </form>
    </Card>
  );
}

function SessionsCard() {
  const logoutAll = useMutation({
    mutationFn: () => call(api.POST("/api/v1/auth/logout-all")),
    onSuccess: () => setAccessToken(null),
  });
  return (
    <Card title="Sessions">
      <ErrorAlert error={logoutAll.error} />
      <p className="muted small">
        Déconnecte immédiatement tous vos appareils (à utiliser en cas de perte ou de doute).
      </p>
      <button className="btn" disabled={logoutAll.isPending} onClick={() => logoutAll.mutate()}>
        Se déconnecter partout
      </button>
    </Card>
  );
}

function PrivacyCard() {
  const user = useCurrentUser();
  const [exported, setExported] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const exportData = useMutation({
    mutationFn: () => call(api.GET("/api/v1/users/me/export")),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `mes-donnees-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setExported(true);
    },
  });
  const erase = useMutation({
    mutationFn: () => call(api.DELETE("/api/v1/users/me")),
    onSuccess: () => setAccessToken(null),
  });
  return (
    <Card title="Mes données personnelles (RGPD)">
      <ErrorAlert error={exportData.error ?? erase.error} />
      {exported && <SuccessAlert>Export téléchargé.</SuccessAlert>}
      <p className="muted small">
        Téléchargez l'ensemble des données personnelles vous concernant (profil, tickets créés, actions
        réalisées) au format JSON.
      </p>
      <button className="btn" disabled={exportData.isPending} onClick={() => exportData.mutate()}>
        Exporter mes données
      </button>
      {user.role !== "admin" && (
        <div className="danger-zone">
          <h3>Supprimer mon compte</h3>
          <p className="muted small">
            Vos nom, e-mail et téléphone seront effacés de façon irréversible. Les interventions que vous
            avez déclarées sont conservées (obligation de traçabilité des ERP) mais ne seront plus liées à
            votre identité. Tapez <strong>SUPPRIMER</strong> pour confirmer.
          </p>
          <div className="inline-form">
            <input aria-label="Confirmation" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
            <button
              className="btn btn-danger"
              disabled={confirmText !== "SUPPRIMER" || erase.isPending}
              onClick={() => erase.mutate()}
            >
              Supprimer mon compte
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
