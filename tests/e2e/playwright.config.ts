import { defineConfig, devices } from "@playwright/test";

// Runs against the compose stack (seeded). BASE_URL defaults to Caddy; the local CA may be untrusted.
export default defineConfig({
  testDir: ".",
  testIgnore: ["**/._*", "**/node_modules/**"],
  timeout: 60_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "https://enclave.localhost",
    ignoreHTTPSErrors: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
});
