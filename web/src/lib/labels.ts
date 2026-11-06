import type { Role } from "./types";

export const ROLE_LABEL: Record<Role, string> = {
  tenant_admin: "Admin",
  operator: "Operator",
  viewer: "Viewer",
};

export const ROLE_HINT: Record<Role, string> = {
  tenant_admin: "Manages cameras, people and settings, and sees every camera.",
  operator: "Watches assigned cameras and handles alerts.",
  viewer: "Watches assigned cameras only.",
};

const ACTIONS: Record<string, string> = {
  "auth.login": "Signed in",
  "auth.login_failed": "Failed sign-in",
  "auth.logout": "Signed out",
  "auth.switch_tenant": "Switched organisation",
  "auth.refresh_reuse": "Session ended for safety",
  "live.view": "Opened live view",
  "camera.create": "Added a camera",
  "camera.update": "Changed a camera",
  "camera.delete": "Removed a camera",
  "member.add": "Added a member",
  "member.role_change": "Changed a role",
  "member.remove": "Removed a member",
  "site.create": "Added a site",
  "tenant.create": "Organisation created",
};

export function actionLabel(action: string): string {
  return ACTIONS[action] ?? action;
}

export function relativeTime(iso: string, now = Date.now()): string {
  const s = Math.round((now - new Date(iso).getTime()) / 1000);
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
