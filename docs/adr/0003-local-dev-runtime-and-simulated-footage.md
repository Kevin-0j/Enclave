# 0003 — Local runtime and simulated footage

Status: accepted (M1) · 2026-11-06

## Decision

- **Container runtime:** Colima (MIT, headless) on the lead's Mac instead of Docker Desktop. The
  compose file is runtime-neutral.
- **Local TLS:** Caddy `tls internal` on `https://enclave.localhost` (`*.localhost` resolves to
  127.0.0.1). `scripts/trust-ca.sh` adds Caddy's root to the macOS keychain. Vite dev on
  `http://localhost:5173` is also a secure context, so service workers and Web Push work there too.
- **Footage:** the simulator uses any `*.mp4` dropped into `sim/clips/` (licensed or royalty-free
  stock, see `sim/README.md`). Without clips it renders synthetic scenes with FFmpeg so the demo
  never depends on a download. One synthetic clip has motion at known times (10–15 s and 40–45 s of a
  60 s loop) for M4 tests.
- **CPU budget:** each camera's 1080p loop is rendered once and published with `-c copy`; the 360p
  sub-stream is encoded live with a burned-in wall clock, which also serves the NFR1 latency check.
  H.264, no B-frames, 1 s GOP for fast WebRTC start.
- **Fixed demo IDs:** `sim/cameras.json` holds the demo tenant and camera UUIDs; the seed script and
  the simulator both read it, so media paths match without a lookup.
- **No bind mounts for config:** the dev SSD is exFAT, which presents every file as mode 0700 owned
  by the Mac user, so non-root containers cannot read bind-mounted files. Config is copied into
  images with `COPY --chmod` (build context = repo root). Data lives in named volumes.
