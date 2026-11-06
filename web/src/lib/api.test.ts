import { api, refreshSession, setSession } from "./api";

const session = {
  access_token: "fresh",
  expires_in: 900,
  user: { id: "u", email: "a@b.c", name: "", is_platform_admin: false },
  tenant: null,
  role: null,
  permissions: [],
  memberships: [],
};

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.restoreAllMocks();
  setSession(null);
});

it("refreshes once on 401 and retries with the new token", async () => {
  const calls: { url: string; auth?: string }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const auth = (init?.headers as Record<string, string> | undefined)?.Authorization;
    calls.push({ url, auth });
    if (url.endsWith("/auth/refresh")) return json(200, session);
    return auth === "Bearer fresh" ? json(200, { ok: true }) : json(401, { detail: "expired" });
  });
  await expect(api<{ ok: boolean }>("/api/v1/cameras")).resolves.toEqual({ ok: true });
  expect(calls.map((c) => c.url)).toEqual(["/api/v1/cameras", "/api/v1/auth/refresh", "/api/v1/cameras"]);
});

it("shares one refresh between concurrent callers", async () => {
  const spy = vi.spyOn(globalThis, "fetch").mockImplementation(async () => json(200, session));
  await Promise.all([refreshSession(), refreshSession(), refreshSession()]);
  expect(spy).toHaveBeenCalledTimes(1);
});

it("surfaces RFC 9457 problem details", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => json(403, { status: 403, detail: "Your role does not allow this." }));
  await expect(api("/api/v1/users", {}, false)).rejects.toMatchObject({ status: 403, message: "Your role does not allow this." });
});
