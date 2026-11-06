# Enclave

Multi-tenant, vendor-neutral CCTV monitoring and alerting for Kenyan property operators.
Live view over WebRTC, recordings and playback, motion alerts, roles and a full audit trail,
with tenant isolation enforced in the database and at the media server.

**Status:** milestone 1 (vertical slice): two isolated demo tenants, simulated cameras, sign-in,
camera management, live 2×2 / 3×3 grids over WebRTC with HLS fallback, full-quality maximise,
per-camera permissions, audit log, and the cross-tenant isolation test suite.

## Run it

Requires Docker (Colima or Docker Desktop), Node 22, Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env && ./scripts/gen-secrets.sh
./scripts/up.sh
docker compose exec api python -m app.seed
./scripts/trust-ca.sh        # optional, removes the certificate warning
open https://enclave.localhost
```

Demo accounts (password is `SEED_PASSWORD` in `.env`):

| Account | Tenant | Sees |
|---|---|---|
| `admin@mlima.demo` | Mlima Residences | all 4 cameras, people, activity |
| `viewer@mlima.demo` | Mlima Residences | 3 granted cameras only |
| `admin@ngong.demo` | Ngong Road Offices | its own 2 cameras, nothing of Mlima |
| `platform@enclave.demo` | platform | tenant management API, no tenant data |

## Layout

`api/` FastAPI · `web/` React PWA · `sim/` FFmpeg cameras · `infra/` Caddy, MediaMTX, Postgres ·
`tests/e2e/` Playwright · `docs/` build pack and ADRs. See `CLAUDE.md` for rules and commands.

## Architecture in one paragraph

Browsers talk only to Caddy. The API issues a 60-second stream token per camera, bound to user,
tenant, camera and stream variant; MediaMTX asks the API's private auth hook before any read or
publish, and the hook re-checks the token, membership and camera grant in PostgreSQL under
row-level security. The app's database role cannot bypass RLS, so a missing tenant filter returns
nothing rather than someone else's data. Camera addresses are envelope-encrypted and write-only.
