import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { setSession } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";
import type { Session } from "@/lib/types";
import { AppShell } from "./AppShell";

function sessionWith(permissions: string[]): Session {
  return {
    access_token: "t",
    expires_in: 900,
    user: { id: "u", email: "viewer@mlima.demo", name: "Viewer", is_platform_admin: false },
    tenant: { id: "t1", name: "Mlima Residences", slug: "mlima", region: "ke", retention_days: 7, status: "active" },
    role: "viewer",
    permissions,
    memberships: [],
  };
}

async function renderShell(permissions: string[]) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify(sessionWith(permissions)), { status: 200 }));
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AuthProvider>
          <AppShell />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findAllByText("Mlima Residences");
}

afterEach(() => {
  vi.restoreAllMocks();
  setSession(null);
});

it("shows viewers only what they may use", async () => {
  await renderShell(["live:view", "cameras:read"]);
  expect(screen.getAllByRole("link", { name: /live/i }).length).toBeGreaterThan(0);
  expect(screen.queryByRole("link", { name: /people/i })).toBeNull();
  expect(screen.queryByRole("link", { name: /activity/i })).toBeNull();
});

it("shows admins people and activity", async () => {
  await renderShell(["live:view", "cameras:read", "users:read", "audit:read"]);
  expect(screen.getAllByRole("link", { name: /people/i }).length).toBeGreaterThan(0);
  expect(screen.getAllByRole("link", { name: /activity/i }).length).toBeGreaterThan(0);
});
