# 0002 — Media authentication, stream tokens and media nodes

Status: accepted (M1) · 2026-11-06

## Context

MediaMTX 1.21.3 with `authMethod: http` POSTs `user, password, token, ip, action, path, protocol,
id, query, userAgent` to `authHTTPAddress` for every publish/read/playback/api request; 2xx allows.
WebRTC (WHEP) and HLS clients send credentials as `Authorization: Bearer <token>`. MediaMTX
authenticates when a session is *created*; later requests on that session are not re-checked
(v1.21.1 release notes). The response may carry `{"expireAt": ...}` to end the session.

## Decision

- **Stream token:** HS256 JWT, own secret (`STREAM_TOKEN_SECRET`), 60 s lifetime, claims
  `sub` (user), `tid` (tenant), `cid` (camera), `var` (main|sub), `act` (read), `jti`. Issued by
  `POST /api/v1/cameras/{id}/stream` after the RBAC check, the rate limit and an audit record.
- **Hook** (`POST /internal/media/auth`): parses `path` with a strict regex, then
  - `read` over webrtc/hls: token must verify, and its `tid/cid/var` must equal the path; the camera
    must exist and be enabled under that tenant's RLS context; the membership must still exist.
  - `publish`: only the simulator credential (`SIM_PUBLISH_USER/PASS`, constant-time compare) for a
    camera whose `source_type = 'sim'`; gateway credentials arrive in M6.
  - `playback`, `api`, `metrics`: only the internal service credential (the API proxies `/list` and
    `/get`, so browsers never call the playback server directly).
  - Anything else → 403. Decisions are logged without secrets.
- **Private network:** Caddy never routes `/internal/*`, and the API rejects hook calls whose client
  IP is outside `MEDIA_HOOK_ALLOWED_CIDRS` (the `media` Docker network only).
- **Long sessions:** tokens only open sessions, so a 60 s token does not cut a viewer off after 60 s.
  Revoking a live session after a permission change uses the MediaMTX control API (M2).
- **Media nodes:** `media_nodes(id, name, region, webrtc_base_url, hls_base_url, internal_url)`;
  every camera has `media_node_id`. URLs are built from the row, so adding a node is a data change.
- **Concurrent stream cap:** M1 rate-limits token issuance per user. A hard concurrent cap needs
  reader tracking (`runOnRead`/`runOnUnread` hooks or the control API) and lands in M2.

## Consequences

Tenant isolation on video is enforced at the media server, not just the API. ICE/media traffic goes
over UDP 8189 straight to MediaMTX (Caddy cannot proxy it); only signalling passes through Caddy.
