/**
 * Live player engine: WebRTC via WHEP first (sub-second latency), HLS via hls.js as the fallback for
 * networks that block UDP. Each (re)connect asks the API for a fresh 60 s stream token; MediaMTX only
 * checks it when the session opens (ADR 0002), so an open stream keeps playing past 60 s.
 */
import type { StreamGrant } from "./types";

export type PlayerState = "connecting" | "playing" | "retrying" | "error";
export type Transport = "webrtc" | "hls";

export interface PlayerHandle {
  stop: () => void;
}

interface Options {
  video: HTMLVideoElement;
  getGrant: () => Promise<StreamGrant>;
  onState: (state: PlayerState, info?: { transport?: Transport; message?: string }) => void;
  preferHls?: boolean;
}

const ICE_GATHER_TIMEOUT_MS = 1500;
const RETRY_DELAYS_MS = [1000, 2000, 5000, 10000];

/** Resolve the WHEP session URL. MediaMTX answers with a path relative to its own root, which sits under
 *  /media behind Caddy and the Vite proxy. */
export function resolveSessionUrl(whepUrl: string, location: string | null): string | null {
  if (!location) return null;
  if (/^https?:\/\//.test(location)) return location;
  const base = new URL(whepUrl, window.location.origin);
  const prefix = base.pathname.split("/t/")[0] ?? "";
  if (location.startsWith("/t/")) return `${base.origin}${prefix}${location}`;
  return new URL(location, base).toString();
}

function waitForIce(pc: RTCPeerConnection): Promise<void> {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      pc.removeEventListener("icegatheringstatechange", check);
      resolve();
    };
    const check = () => pc.iceGatheringState === "complete" && done();
    pc.addEventListener("icegatheringstatechange", check);
    window.setTimeout(done, ICE_GATHER_TIMEOUT_MS); // host candidates are enough on LAN / same host
  });
}

async function startWhep(video: HTMLVideoElement, grant: StreamGrant, onFail: (msg: string) => void) {
  const pc = new RTCPeerConnection({ bundlePolicy: "max-bundle" });
  pc.addTransceiver("video", { direction: "recvonly" });
  pc.addTransceiver("audio", { direction: "recvonly" });
  pc.ontrack = (e) => {
    if (e.track.kind !== "video") return;
    video.srcObject = e.streams[0] ?? new MediaStream([e.track]);
  };
  pc.onconnectionstatechange = () => {
    if (pc.connectionState === "failed" || pc.connectionState === "disconnected") onFail(pc.connectionState);
  };
  await pc.setLocalDescription(await pc.createOffer());
  await waitForIce(pc);
  const res = await fetch(grant.whep_url, {
    method: "POST",
    headers: { "Content-Type": "application/sdp", Authorization: `Bearer ${grant.token}` },
    body: pc.localDescription?.sdp ?? "",
  });
  if (res.status !== 201) {
    pc.close();
    throw new Error(res.status === 401 || res.status === 403 ? "denied" : `whep ${res.status}`);
  }
  const session = resolveSessionUrl(grant.whep_url, res.headers.get("Location"));
  await pc.setRemoteDescription({ type: "answer", sdp: await res.text() });
  return () => {
    // End the session server-side first; closing the peer connection first makes the DELETE a 404.
    if (session) void fetch(session, { method: "DELETE" }).catch(() => undefined);
    pc.close();
  };
}

async function startHls(video: HTMLVideoElement, grant: StreamGrant, onFail: (msg: string) => void) {
  const { default: Hls } = await import("hls.js"); // only downloaded when WebRTC fails
  if (!Hls.isSupported()) throw new Error("hls unsupported");
  const hls = new Hls({
    lowLatencyMode: true,
    backBufferLength: 10,
    xhrSetup: (xhr) => xhr.setRequestHeader("Authorization", `Bearer ${grant.token}`),
  });
  hls.on(Hls.Events.ERROR, (_e, data) => data.fatal && onFail(data.details));
  hls.loadSource(grant.hls_url);
  hls.attachMedia(video);
  return () => hls.destroy();
}

export function play({ video, getGrant, onState, preferHls = false }: Options): PlayerHandle {
  let stopped = false;
  let teardown: (() => void) | null = null;
  let attempt = 0;
  let timer: number | undefined;
  let useHls = preferHls;

  const cleanup = () => {
    teardown?.();
    teardown = null;
    video.srcObject = null;
    video.removeAttribute("src");
  };

  const retry = (message: string) => {
    if (stopped) return;
    cleanup();
    if (message === "denied") {
      onState("error", { message: "You don't have access to this camera." });
      return;
    }
    // After a failed WebRTC attempt, try HLS before backing off.
    if (!useHls) useHls = true;
    const delay = RETRY_DELAYS_MS[Math.min(attempt, RETRY_DELAYS_MS.length - 1)] ?? 10000;
    attempt += 1;
    onState(attempt > 6 ? "error" : "retrying", { message: "Reconnecting…" });
    if (attempt > 6) return;
    timer = window.setTimeout(connect, delay);
  };

  const connect = async () => {
    if (stopped) return;
    onState(attempt === 0 ? "connecting" : "retrying");
    try {
      const grant = await getGrant();
      if (stopped) return;
      const transport: Transport = useHls ? "hls" : "webrtc";
      teardown = transport === "hls" ? await startHls(video, grant, retry) : await startWhep(video, grant, retry);
      if (stopped) return cleanup();
      const onPlaying = () => {
        attempt = 0;
        onState("playing", { transport });
      };
      video.addEventListener("playing", onPlaying, { once: true });
      void video.play().catch(() => undefined);
    } catch (err) {
      retry(err instanceof Error ? err.message : "failed");
    }
  };

  void connect();
  return {
    stop: () => {
      stopped = true;
      window.clearTimeout(timer);
      cleanup();
    },
  };
}
