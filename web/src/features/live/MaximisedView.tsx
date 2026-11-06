import * as RD from "@radix-ui/react-dialog";
import { ChevronLeft, ChevronRight, Maximize, X } from "lucide-react";
import { useRef } from "react";
import { IconButton } from "@/components/ui/Button";
import type { Camera } from "@/lib/types";
import { StreamOverlay } from "./CameraTile";
import { useLiveStream } from "./useLiveStream";

/** One camera on the main (full-quality) stream. Arrow keys step through cameras. */
export function MaximisedView({ cameras, index, onIndex, onClose }: { cameras: Camera[]; index: number; onIndex: (i: number) => void; onClose: () => void }) {
  const camera = cameras[index];
  const stageRef = useRef<HTMLDivElement>(null);
  const { videoRef, status, retry } = useLiveStream(camera?.id ?? "", "main", !!camera);
  if (!camera) return null;
  const step = (d: number) => onIndex((index + d + cameras.length) % cameras.length);

  return (
    <RD.Root open onOpenChange={(o) => !o && onClose()}>
      <RD.Portal>
        <RD.Overlay className="fixed inset-0 z-50 bg-[#030508]" />
        <RD.Content
          aria-describedby={undefined}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") step(1);
            if (e.key === "ArrowLeft") step(-1);
          }}
          className="fixed inset-0 z-50 flex flex-col pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] outline-none"
        >
          <div className="flex h-14 items-center gap-2 px-3 text-white sm:px-5">
            <RD.Title className="min-w-0 flex-1 truncate text-[15px] font-medium">
              {camera.name} <span className="text-white/50">· full quality</span>
            </RD.Title>
            <IconButton label="Browser full screen" variant="overlay" size="sm" onClick={() => void stageRef.current?.requestFullscreen?.()}>
              <Maximize aria-hidden className="size-4" />
            </IconButton>
            <RD.Close asChild>
              <IconButton label="Close" variant="overlay" size="sm">
                <X aria-hidden className="size-4" />
              </IconButton>
            </RD.Close>
          </div>
          <div className="relative flex min-h-0 flex-1 items-center justify-center px-0 sm:px-5 sm:pb-5">
            <div ref={stageRef} className="relative aspect-video max-h-full w-full max-w-[min(100%,calc((100dvh-7rem)*16/9))] overflow-hidden bg-stage sm:rounded-2xl">
              <video key={camera.id} ref={videoRef} muted playsInline autoPlay className="absolute inset-0 size-full object-contain" aria-label={`Live view: ${camera.name}`} />
              <StreamOverlay camera={camera} state={status.state} transport={status.transport} message={status.message} onRetry={retry} large />
            </div>
            {cameras.length > 1 && (
              <>
                <IconButton label="Previous camera" variant="overlay" className="absolute top-1/2 left-2 -translate-y-1/2 sm:left-7" onClick={() => step(-1)}>
                  <ChevronLeft aria-hidden className="size-5" />
                </IconButton>
                <IconButton label="Next camera" variant="overlay" className="absolute top-1/2 right-2 -translate-y-1/2 sm:right-7" onClick={() => step(1)}>
                  <ChevronRight aria-hidden className="size-5" />
                </IconButton>
              </>
            )}
          </div>
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}
