import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const env = Object.fromEntries(
  readFileSync(new URL("../../.env", import.meta.url), "utf8")
    .split("\n")
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const PASSWORD = env.SEED_PASSWORD as string;

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/live$/);
}

/** True once the <video> has decoded real frames (not just attached). */
async function playingCount(page: Page): Promise<number> {
  return page.$$eval("video", (vs) => vs.filter((v) => (v as HTMLVideoElement).readyState >= 2 && (v as HTMLVideoElement).videoWidth > 0).length);
}

test("tenant admin sees a live 2x2 grid of their own cameras", async ({ page }, info) => {
  await signIn(page, "admin@mlima.demo");
  await page.getByRole("radio", { name: /2 × 2/ }).click().catch(() => undefined);
  await expect(page.getByLabel(/^Live view:/)).toHaveCount(4);
  await expect(page.getByText("Main gate")).toBeVisible();
  await expect(page.getByText("Reception")).toHaveCount(0); // tenant B's camera never appears
  await expect.poll(() => playingCount(page), { timeout: 30_000 }).toBeGreaterThanOrEqual(info.project.name === "phone" ? 1 : 4);
  await page.screenshot({ path: `screenshots/live-${info.project.name}.png`, fullPage: false });
});

test("maximising a tile switches to the full-quality stream", async ({ page }, info) => {
  await signIn(page, "admin@mlima.demo");
  await page.getByRole("button", { name: "Open Main gate full screen" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("full quality")).toBeVisible();
  await expect.poll(() => dialog.locator("video").evaluate((v: HTMLVideoElement) => v.videoWidth), { timeout: 30_000 }).toBe(1920);
  await page.screenshot({ path: `screenshots/maximised-${info.project.name}.png` });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("viewer only sees granted cameras and no admin pages", async ({ page }) => {
  await signIn(page, "viewer@mlima.demo");
  await expect(page.getByLabel(/^Live view:/)).toHaveCount(3);
  await expect(page.getByText("North perimeter")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "People" })).toHaveCount(0);
  await page.goto("/people");
  await expect(page).toHaveURL(/\/live$/);
});

test("the other tenant is fully separate", async ({ page }, info) => {
  await signIn(page, "admin@ngong.demo");
  await expect(page.getByLabel(/^Live view:/)).toHaveCount(2);
  await expect(page.getByText("Main gate")).toHaveCount(0);
  await page.goto("/activity");
  await expect(page.getByRole("heading", { name: "Activity" })).toBeVisible();
  await expect(page.getByText("admin@mlima.demo")).toHaveCount(0);
  await page.screenshot({ path: `screenshots/activity-${info.project.name}.png` });
});

test("sign-in page", async ({ page }, info) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await page.screenshot({ path: `screenshots/login-${info.project.name}.png` });
});
