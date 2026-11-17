/**
 * Access-token holder. The access token lives in memory only (never in Web Storage);
 * the refresh token is an HttpOnly cookie that JavaScript cannot read.
 */
import type { TokenPair } from "./types";

const API = "/api/v1";
let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
const listeners = new Set<(authenticated: boolean) => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  const changed = (token === null) !== (accessToken === null);
  accessToken = token;
  if (changed) listeners.forEach((listener) => listener(token !== null));
}

export function onSessionChange(listener: (authenticated: boolean) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${API}/auth/refresh`, { method: "POST", credentials: "same-origin" })
    .then(async (response) => {
      if (!response.ok) {
        setAccessToken(null);
        return false;
      }
      const pair = (await response.json()) as TokenPair;
      setAccessToken(pair.access_token);
      return true;
    })
    .catch(() => {
      setAccessToken(null);
      return false;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** fetch() with the bearer token; on 401, refreshes once and replays the request. */
export async function authFetch(input: Request | string, init?: RequestInit): Promise<Response> {
  const target = typeof input === "string" ? new URL(input, window.location.origin).href : input;
  const request = new Request(target, { credentials: "same-origin", ...init });
  const replay = request.clone();
  const withToken = (req: Request): Request => {
    const token = getAccessToken();
    if (token) req.headers.set("Authorization", `Bearer ${token}`);
    return req;
  };
  const response = await fetch(withToken(request));
  if (response.status !== 401 || request.url.includes("/auth/")) return response;
  return (await refreshSession()) ? fetch(withToken(replay)) : response;
}

export async function login(email: string, password: string): Promise<Response> {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${API}/auth/login`, {
    method: "POST",
    body,
    credentials: "same-origin",
  });
  if (response.ok) setAccessToken(((await response.json()) as TokenPair).access_token);
  return response;
}

export async function logout(): Promise<void> {
  try {
    await authFetch(`${API}/auth/logout`, { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}
