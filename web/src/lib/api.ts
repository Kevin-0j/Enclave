/**
 * API client. The access token lives only in memory (never localStorage). A 401 triggers one silent
 * refresh through the HttpOnly cookie, shared by every request in flight, then a single retry.
 */
import type { Problem, Session } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem | null;
  constructor(status: number, problem: Problem | null) {
    super(problem?.detail ?? `Request failed (${status})`);
    this.status = status;
    this.problem = problem;
  }
}

type Listener = (session: Session | null) => void;

let accessToken: string | null = null;
let refreshing: Promise<Session | null> | null = null;
const listeners = new Set<Listener>();

export function setSession(session: Session | null): void {
  accessToken = session?.access_token ?? null;
  listeners.forEach((l) => l(session));
}

export function onSession(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

async function parse(res: Response): Promise<never> {
  let problem: Problem | null = null;
  try {
    problem = (await res.json()) as Problem;
  } catch {
    /* not JSON */
  }
  throw new ApiError(res.status, problem);
}

export function refreshSession(): Promise<Session | null> {
  refreshing ??= fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin" })
    .then(async (res) => {
      if (!res.ok) return null;
      return (await res.json()) as Session;
    })
    .catch(() => null)
    .then((session) => {
      setSession(session);
      return session;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(path, {
    method: init.method ?? "GET",
    headers,
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    credentials: "same-origin",
  });
  if (res.status === 401 && retry && !path.startsWith("/api/v1/auth/")) {
    const session = await refreshSession();
    if (session) return api<T>(path, init, false);
  }
  if (!res.ok) return parse(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
