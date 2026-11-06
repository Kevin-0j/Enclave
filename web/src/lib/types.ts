/** Mirrors api/app/schemas.py. Camera URLs never appear: the API does not return them. */
export type Role = "tenant_admin" | "operator" | "viewer";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  region: string;
  retention_days: number;
  status: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  is_platform_admin: boolean;
}

export interface Session {
  access_token: string;
  expires_in: number;
  user: User;
  tenant: Tenant | null;
  role: Role | null;
  permissions: string[];
  memberships: { tenant: Tenant; role: Role }[];
}

export interface Camera {
  id: string;
  name: string;
  site_id: string | null;
  source_type: "sim" | "rtsp" | "gateway";
  enabled: boolean;
  status: "unknown" | "online" | "offline";
  last_seen: string | null;
  ptz_capable: boolean;
  has_sub_stream: boolean;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Site {
  id: string;
  name: string;
  address: string;
  timezone: string;
}

export interface Member {
  user_id: string;
  email: string;
  name: string;
  role: Role;
  joined_at: string;
}

export interface StreamGrant {
  whep_url: string;
  hls_url: string;
  token: string;
  expires_at: string;
  variant: "main" | "sub";
}

export interface AuditEntry {
  id: string;
  at: string;
  user_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  ip: string | null;
  detail: Record<string, unknown>;
}

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  request_id?: string;
  errors?: { loc: (string | number)[]; msg: string }[];
}
