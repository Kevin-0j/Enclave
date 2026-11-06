# 0001 — Tenancy context and RLS for tables without a single tenant

Status: accepted (M1) · 2026-11-06

## Context

Part C protects tenant-owned tables with `tenant_id = current_setting('app.tenant_id')::uuid`.
Several tables are not owned by one tenant: `tenants`, `users` (a person can belong to more than
one tenant), `memberships` (must be found at login, before a tenant is chosen), `refresh_tokens`,
and `media_nodes` (platform infrastructure, missing from C.3 but required by the scalability rules).
Part C also needs platform admins to create tenants while the app role has no BYPASSRLS.

## Decision

One database role for the app (`enclave_app`, LOGIN, NOBYPASSRLS, not the owner). Every table has
RLS enabled and forced. Context is set per transaction with `set_config(key, value, true)`:

| GUC | Set when |
|---|---|
| `app.tenant_id` | an authenticated request acts in a tenant (from the access token) |
| `app.user_id` | any authenticated request |
| `app.login_email` | only inside the login / invite lookup transaction |
| `app.refresh_hash` | only inside the refresh transaction |
| `app.platform_admin` | `'on'` only for a verified platform admin on `/api/v1/tenants` routes |

Policies (all default-deny when the GUC is unset, via `nullif(current_setting(k, true), '')`):

- tenant-owned tables: `tenant_id = app.tenant_id`
- `tenants`: `id = app.tenant_id OR app.platform_admin = 'on'`
- `memberships`: `tenant_id = app.tenant_id OR user_id = app.user_id`
- `users`: `id = app.user_id OR email = app.login_email OR` member of `app.tenant_id`
- `refresh_tokens`: `user_id = app.user_id OR token_hash = app.refresh_hash`
- `media_nodes`: read-only for the app role (no INSERT/UPDATE/DELETE grant)

A platform admin who needs to act *inside* a tenant (for example to seed its first admin) sets
`app.tenant_id` to that tenant in the same transaction; it is audited. The platform-admin flag
never widens any tenant-owned table.

## Consequences

A missing `set_config` call returns empty results instead of leaking data. The isolation suite
tests every policy. Login needs two short transactions (lookup by email, then the session).
