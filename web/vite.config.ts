/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

// Dev server: http://localhost:5173 (a secure context, so service worker + Web Push work).
// /api goes to the API container, /media (WHEP) and /hls straight to MediaMTX, like Caddy does.
// MediaMTX replies with root-relative Location headers; restore the mount prefix (Caddy does the same).
const prefixLocation = (prefix: string) => (proxy: { on: (e: "proxyRes", cb: (res: { headers: Record<string, unknown> }) => void) => void }) =>
  proxy.on("proxyRes", (res) => {
    const loc = res.headers.location;
    if (typeof loc === "string" && loc.startsWith("/t/")) res.headers.location = prefix + loc;
  });

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/media": { target: "http://127.0.0.1:8889", rewrite: (p) => p.replace(/^\/media/, ""), configure: prefixLocation("/media") },
      "/hls": { target: "http://127.0.0.1:8888", rewrite: (p) => p.replace(/^\/hls/, ""), configure: prefixLocation("/hls") },
    },
  },
  build: { sourcemap: false, target: "es2022" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["**/._*", "**/node_modules/**"],
    css: false,
  },
});
