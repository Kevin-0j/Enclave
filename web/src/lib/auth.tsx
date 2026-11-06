import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, onSession, refreshSession, setSession } from "./api";
import type { Session } from "./types";

interface AuthValue {
  session: Session | null;
  ready: boolean;
  signIn: (email: string, password: string) => Promise<Session>;
  signOut: () => Promise<void>;
  switchTenant: (tenantId: string) => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setLocal] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const qc = useQueryClient();

  useEffect(() => onSession(setLocal), []);

  // On load, try the refresh cookie. No cookie means the sign-in screen.
  useEffect(() => {
    void refreshSession().finally(() => setReady(true));
  }, []);

  // Refresh the access token a minute before it expires, so video tiles never hit a 401 mid-request.
  useEffect(() => {
    if (!session) return;
    const ms = Math.max(30_000, (session.expires_in - 60) * 1000);
    const id = window.setTimeout(() => void refreshSession(), ms);
    return () => window.clearTimeout(id);
  }, [session]);

  const signIn = useCallback(async (email: string, password: string) => {
    const s = await api<Session>("/api/v1/auth/login", { method: "POST", body: { email, password } });
    setSession(s);
    return s;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api("/api/v1/auth/logout", { method: "POST" });
    } finally {
      setSession(null);
      qc.clear();
    }
  }, [qc]);

  const switchTenant = useCallback(
    async (tenantId: string) => {
      const s = await api<Session>("/api/v1/auth/switch-tenant", { method: "POST", body: { tenant_id: tenantId } });
      qc.clear(); // nothing from the previous tenant may linger in the cache
      setSession(s);
    },
    [qc],
  );

  const value = useMemo<AuthValue>(
    () => ({
      session,
      ready,
      signIn,
      signOut,
      switchTenant,
      can: (p) => session?.permissions.includes(p) ?? false,
    }),
    [session, ready, signIn, signOut, switchTenant],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
