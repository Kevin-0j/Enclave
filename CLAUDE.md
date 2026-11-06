# Enclave — working notes for Claude Code

Multi-tenant, vendor-neutral CCTV monitoring and alerting for Kenyan property operators
(offices, gated communities, short-stay operators). Team: Kevin Ojwang (lead), Victor Boore.

**Specification:** `docs/enclave-build-pack.pdf`, Part C. Parts A/B hold the decisions and the
framework research. If the spec is wrong or unclear, stop and raise it before deviating. Gaps we
have resolved are recorded as ADRs in `docs/adr/` — read them before changing the data model,
auth or media flow.

## Stack (do not substitute without asking)

| Layer | Choice |
|---|---|
| Infra | Docker Compose, Caddy (TLS, internal CA for local dev), MediaMTX 1.21.3 |
| Simulator | FFmpeg publishing looped clips as RTSP main (1080p) + sub (360p) |
| API | Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, Pydantic v2, Argon2id, JWT (15 min) + rotating refresh cookie |
| Workers | Python: motion (OpenCV), notifier (Redis streams, consumer groups), retention |
| Web | React + TypeScript + Vite PWA, TanStack Query, Tailwind v4, WHEP player + hls.js fallback |
| Edge (M6) | Python agent, onvif-zeep-async, MediaMTX pulling LAN RTSP and pushing over SRT |
| Data | PostgreSQL 16 with RLS; Redis 7.2 (BSD licence; Valkey is a drop-in) |

## Repo layout

```
api/        FastAPI app (app/), Alembic migrations (alembic/), pytest (tests/)
web/        React PWA
workers/    motion, notifier, retention workers (M3/M4)
edge/       gateway agent (M6)
infra/      compose-related config: caddy/, mediamtx/, postgres/ (role bootstrap)
sim/        FFmpeg camera simulator + cameras.json (fixed demo IDs shared with the seed)
docs/       build pack, adr/
tests/e2e/  Playwright end-to-end tests
scripts/    dev helpers (seed, trust local CA)
```

## Commands

```bash
colima start --cpu 4 --memory 4                  # Docker runtime on the lead's Mac
cp .env.example .env && ./scripts/gen-secrets.sh # once: random secrets; SEED_PASSWORD = demo login
./scripts/up.sh                                  # clears ._* files, then docker compose up -d --build
docker compose exec api python -m app.seed       # two demo tenants + 6 simulated cameras (idempotent)
./scripts/trust-ca.sh                            # once, asks for sudo: trust Caddy's local CA
open https://enclave.localhost                   # the app behind Caddy (strict CSP, TLS)
./scripts/smoke-isolation.sh                     # end-to-end cross-tenant checks through the real stack

# API (from api/). The venv lives off the exFAT SSD (AppleDouble files break wheel installs):
export UV_PROJECT_ENVIRONMENT=$HOME/.cache/enclave/api-venv UV_LINK_MODE=copy
uv sync && uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run pytest                                    # real Postgres/Redis from compose (127.0.0.1:55432/56379)

# Web (from web/)
npm ci && npm run lint && npm run typecheck && npm test && npm run build
npm run dev                                      # http://localhost:5173, proxies /api /media /hls to compose

# E2E (from tests/e2e/, stack running and seeded): desktop + Pixel 7 projects
npx playwright test
```

## Non-negotiable security and tenancy rules

1. Every tenant-owned table has `tenant_id` and an RLS policy. The app connects as `enclave_app`
   (no BYPASSRLS, not the table owner) and sets `app.tenant_id` per transaction with
   `set_config(..., true)`. Migrations create the policies. Unset context = no rows.
2. Media paths are `t/{tenant_id}/c/{camera_id}/{main|sub}`. The API issues 60 s stream tokens
   bound to user, tenant, camera, variant and action. The MediaMTX hook
   (`POST /internal/media/auth`, private network only) rejects everything else. Publishing only
   with simulator or gateway credentials.
3. Roles: platform_admin, tenant_admin, operator, viewer + per-camera permissions. Deny by default,
   enforced in one dependency layer (`app/rbac.py`), tested per role and endpoint.
4. Camera URLs/credentials encrypted at rest (envelope encryption, `app/crypto.py`), never returned
   by the API, never logged.
5. Audit every login, live view, playback, export, PTZ command, alert acknowledgement and config
   change in the append-only `audit_log` (no UPDATE/DELETE grants).
6. Rate-limit login and stream requests; cap concurrent streams per user.
7. Secrets only from environment. Commit `.env.example`, never `.env`.
8. Strict CSP (no inline scripts, self-hosted fonts), CORS limited to the app origin, secure
   headers via Caddy.
9. Containers run as non-root; image versions pinned.
10. The cross-tenant isolation suite (`api/tests/test_isolation.py`) covers every endpoint and
    stream URLs. It must pass before a milestone is complete.

## Scalability rules

Stateless API and workers; WebSocket fan-out via Redis pub/sub. Each camera has a `media_node_id`;
the API builds stream URLs from that node's row. Grids use sub-streams; main only when maximised.
Streams on demand. `events`, `alerts`, `audit_log` partitioned by month, indexes lead with
`tenant_id`. Prometheus metrics at `/metrics` (internal), JSON logs with request IDs.

## Working method

- Feature branch per milestone (`m1-vertical-slice`, …), small reviewable commits.
- Tests with the code. Before calling a task done, run lint, type checks and tests and show output.
- Significant decisions → short ADR in `docs/adr/NNNN-title.md`.
- Check current library docs; don't guess APIs. Report when a library differs from the brief.
- Never disable a test or a security control to make something pass.
- No Claude co-author / "generated with" lines in commits or PRs.

## Design system (web)

Borrowed from the team's PaySasa project: CSS tokens in `web/src/index.css` (light/dark via
`data-theme`), hairline cards, Fraunces display + Geist UI + Geist Mono for timecodes, Radix
primitives. Enclave palette: navy ink, one amber accent for the primary action, red only for
LIVE/REC. Mobile first: bottom tab bar under `md`, usable from 360 px, safe-area insets.

## Environment notes

- The dev SSD is exFAT: macOS writes `._*` files (ignored by git). Keep Postgres data in named
  Docker volumes, never bind mounts on the SSD.
- Docker runs via Colima (`colima start`). WebRTC media uses ICE on 8189 (UDP and TCP) straight
  to MediaMTX; signalling goes through Caddy. TCP ICE is what works through the Colima VM.
- BuildKit applies `COPY --chmod` to parent dirs it creates: copy into existing dirs.
- MediaMTX returns root-relative `Location` headers (WHEP sessions, HLS `cookieCheck` redirect);
  Caddy and the Vite proxy re-add the `/media` / `/hls` prefix.
- CSP `style-src` uses a per-request nonce (Caddy `{http.request.uuid}` templated into index.html,
  passed to Radix's style injector with `get-nonce`). Never add `'unsafe-inline'`.
