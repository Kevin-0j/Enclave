import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { setSession } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";
import { LoginPage } from "./LoginPage";

afterEach(() => {
  vi.restoreAllMocks();
  setSession(null);
});

it("shows the server's message when sign-in fails", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const status = String(input).endsWith("/refresh") ? 401 : 401;
    return new Response(JSON.stringify({ status, detail: "That email and password don't match." }), { status });
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), "admin@mlima.demo");
  await user.type(screen.getByLabelText("Password"), "wrong");
  await user.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That email and password don't match.");
});
