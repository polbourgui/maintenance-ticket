import { useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ErrorAlert, Field } from "../components/ui";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login(email.trim(), password);
      // Only same-app paths: never redirect to an attacker-controlled URL.
      navigate(from?.startsWith("/") && !from.startsWith("//") ? from : "/tickets", { replace: true });
    } catch (err) {
      setError(err);
      setPassword("");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="login-page">
      <form className="card login-card" onSubmit={onSubmit}>
        <div className="login-brand">
          <img src="/favicon.svg" alt="" width={40} height={40} />
          <div>
            <h1>Maintenance ERP</h1>
            <p className="muted">Suivi des interventions de vos établissements</p>
          </div>
        </div>
        <ErrorAlert error={error} />
        <Field label="E-mail">
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Mot de passe">
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <button className="btn btn-primary btn-block" disabled={pending}>
          {pending ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </div>
  );
}
