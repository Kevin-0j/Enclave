import { AlertTriangle, Expand, RotateCw, VideoOff } from "lucide-react";
import { useEffect, useState } from "react";
import { IconButton } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import type { Camera } from "@/lib/types";
import { useInView, useLiveStream, usePageVisible } from "./useLiveStream";

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return <>{now.toLocaleTimeString("en-GB", { hour12: false, timeZone: "Africa/Nairobi" })}</>;
}

export function StreamOverlay({
  camera,
  state,
  transport,
  message,
  onRetry,
  large,
}: {
  camera: Camera;
  state: string;
  transport?: string;
  message?: string;
  onRetry: () => void;
  large?: boolean;
}) {
  const playing = state === "playing";
  return (
    <>
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 bg-gradient-to-b from-black/60 to-transparent p-2.5 sm:p-3">
        <span className={cn("flex min-w-0 items-center gap-2 font-medium text-white", large ? "text-[15px]" : "text-[13px]")}>
          <span aria-hidden className={cn("size-2 shrink-0 rounded-full", playing ? "bg-success" : state === "error" ? "bg-danger" : "bg-white/40")} />
          <span className="truncate">{camera.name}</span>
        </span>
        {playing && (
          <span className="flex shrink-0 items-center gap-1.5 rounded-md bg-black/45 px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[11px] text-white/90 backdrop-blur">
            <span aria-hidden className="pulse-dot size-1.5 rounded-full bg-live text-live" />
            LIVE
            {transport === "hls" && <span className="text-white/60" title="WebRTC unavailable; using HLS (a few seconds behind)">· HLS</span>}
            <span className="hidden text-white/60 sm:inline">
              · <Clock />
            </span>
          </span>
        )}
      </div>
      {!playing && (
        <div className="absolute inset-0 grid place-items-center">
          {state === "error" ? (
            <div className="flex flex-col items-center gap-2 px-4 text-center text-white/85">
              <AlertTriangle aria-hidden className="size-5 text-amber" />
              <p className="text-[12.5px]">{message ?? "Can't connect to this camera."}</p>
              <button type="button" onClick={onRetry} className="pointer-events-auto mt-1 inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-[12px] hover:bg-white/20">
                <RotateCw aria-hidden className="size-3.5" /> Try again
              </button>
            </div>
          ) : (
            <p className="text-[12px] text-white/60" role="status">
              {state === "retrying" ? "Reconnecting…" : "Connecting…"}
            </p>
          )}
        </div>
      )}

    </>
  );
}

export function CameraTile({ camera, onMaximise, paused = false }: { camera: Camera; onMaximise: () => void; paused?: boolean }) {
  const { ref, inView } = useInView<HTMLDivElement>();
  const pageVisible = usePageVisible();
  // Streams run only while the tile is on screen, the tab is visible and no camera is maximised.
  const active = inView && pageVisible && camera.enabled && !paused;
  const { videoRef, status, retry } = useLiveStream(camera.id, "sub", active);
  const connecting = status.state === "connecting" || status.state === "retrying";

  return (
    <div
      ref={ref}
      className={cn(
        "group relative aspect-video overflow-hidden rounded-[14px] bg-stage ring-1 ring-border transition-shadow hover:ring-border-strong",
        connecting && "scan",
      )}
    >
      {camera.enabled ? (
        <>
          <video ref={videoRef} muted playsInline autoPlay className="absolute inset-0 size-full object-cover" aria-label={`Live view: ${camera.name}`} />
          <StreamOverlay camera={camera} state={status.state} transport={status.transport} message={status.message} onRetry={retry} />
          <button type="button" onClick={onMaximise} className="absolute inset-0 cursor-zoom-in" aria-label={`Open ${camera.name} full screen`} />
          {/* Touch: the whole tile opens full screen, so the button is a desktop hover affordance only. */}
          <div className="absolute right-2 bottom-10 hidden opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100 sm:block">
            <IconButton label="Full screen" variant="overlay" size="sm" onClick={onMaximise}>
              <Expand aria-hidden className="size-4" />
            </IconButton>
          </div>
        </>
      ) : (
        <div className="absolute inset-0 grid place-items-center text-white/60">
          <span className="flex flex-col items-center gap-2 text-[12.5px]">
            <VideoOff aria-hidden className="size-5" />
            {camera.name} is disabled
          </span>
        </div>
      )}
    </div>
  );
}
