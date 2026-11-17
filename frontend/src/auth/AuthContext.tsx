import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ApiError, api, call, toApiError } from "../api/client";
import * as session from "../api/session";
import type { User } from "../api/types";

type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; user: User };

type AuthContextValue = {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const queryClient = useQueryClient();

  const loadUser = useCallback(async () => {
    const user = await call(api.GET("/api/v1/users/me"));
    setState({ status: "authenticated", user });
  }, []);

  // On start: restore the session from the HttpOnly refresh cookie, if any.
  useEffect(() => {
    let cancelled = false;
    session.refreshSession().then(async (ok) => {
      if (cancelled) return;
      if (!ok) return setState({ status: "anonymous" });
      try {
        await loadUser();
      } catch {
        setState({ status: "anonymous" });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadUser]);

  // Session lost (refresh failed, logout elsewhere): back to the login screen, purge cached data.
  useEffect(
    () =>
      session.onSessionChange((authenticated) => {
        if (!authenticated) {
          queryClient.clear();
          setState({ status: "anonymous" });
        }
      }),
    [queryClient],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      login: async (email, password) => {
        const response = await session.login(email, password);
        if (!response.ok) {
          const body: unknown = await response.json().catch(() => null);
          if (response.status === 401) throw new ApiError(401, "E-mail ou mot de passe incorrect.");
          throw toApiError(response.status, body);
        }
        await loadUser();
      },
      logout: async () => {
        await session.logout();
        queryClient.clear();
        setState({ status: "anonymous" });
      },
      reloadUser: loadUser,
    }),
    [state, loadUser, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

/** The authenticated user (only call inside protected routes). */
export function useCurrentUser(): User {
  const { state } = useAuth();
  if (state.status !== "authenticated") throw new Error("Not authenticated");
  return state.user;
}
