import { useEffect, useRef, useState } from "react";
import { play, type PlayerState, type Transport } from "@/lib/player";
import { requestStream } from "@/lib/queries";

const IDLE: LiveStatus = { state: "idle" };

export interface LiveStatus {
  state: PlayerState | "idle";
  transport?: Transport;
  message?: string;
}

/** Plays a camera into the returned video ref while `active` (visible and enabled). */
export function useLiveStream(cameraId: string, variant: "main" | "sub", active: boolean) {
  // A callback ref (state), not useRef: the <video> may mount a render later, e.g. inside a portal.
  const [video, videoRef] = useState<HTMLVideoElement | null>(null);
  const [status, setStatus] = useState<LiveStatus>({ state: "idle" });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!video || !active) return;
    const handle = play({
      video,
      getGrant: () => requestStream(cameraId, variant),
      onState: (state, info) => setStatus({ state, ...info }),
    });
    return () => {
      handle.stop();
      setStatus({ state: "idle" });
    };
  }, [video, cameraId, variant, active, nonce]);

  // While inactive nothing plays, whatever the last reported state was.
  return { videoRef, status: active ? status : IDLE, retry: () => setNonce((n) => n + 1) };
}

export function useInView<T extends Element>(rootMargin = "120px") {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setInView(entry?.isIntersecting ?? false), { rootMargin });
    io.observe(el);
    return () => io.disconnect();
  }, [rootMargin]);
  return { ref, inView };
}

/** Stop streams while the tab is hidden: saves bandwidth on phones and on the media node. */
export function usePageVisible(): boolean {
  const [visible, setVisible] = useState(() => document.visibilityState !== "hidden");
  useEffect(() => {
    const on = () => setVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  return visible;
}
