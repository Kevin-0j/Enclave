import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setNonce } from "get-nonce";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { AuthProvider } from "./lib/auth";
import { ApiError } from "./lib/api";
import "./index.css";

// Radix's scroll lock injects a <style> element; give it the CSP nonce Caddy issued for this page load.
const nonce = document.querySelector<HTMLMetaElement>('meta[name="csp-nonce"]')?.content ?? "";
if (/^[0-9a-f-]{36}$/.test(nonce)) setNonce(nonce);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
      refetchOnWindowFocus: true,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => void navigator.serviceWorker.register("/sw.js"));
}
