import { ChevronLeft, ChevronRight, Cctv, Grid2x2, Grid3x3, Square } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button, IconButton } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Segmented } from "@/components/ui/Segmented";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { useCameras, useSites } from "@/lib/queries";
import { useSettings, type GridSize } from "@/lib/settings";
import { CameraTile } from "./CameraTile";
import { MaximisedView } from "./MaximisedView";

const GRID_CLASS: Record<GridSize, string> = {
  1: "grid-cols-1 max-w-[1200px]",
  4: "grid-cols-1 sm:grid-cols-2",
  9: "grid-cols-2 lg:grid-cols-3",
};

export function LivePage() {
  const { session, can } = useAuth();
  const { data: cameras, isLoading } = useCameras();
  const { data: sites } = useSites();
  const [settings, update] = useSettings();
  const [page, setPage] = useState(0);
  const [maxIndex, setMaxIndex] = useState<number | null>(null);
  const size = settings.grid;

  const list = useMemo(() => cameras ?? [], [cameras]);
  const pages = Math.max(1, Math.ceil(list.length / size));
  const current = Math.min(page, pages - 1);
  const visible = list.slice(current * size, current * size + size);
  const siteName = sites?.length === 1 ? sites[0]?.name : sites && sites.length > 1 ? `${sites.length} sites` : null;

  return (
    <div className="mx-auto max-w-[1480px] px-4 pt-5 sm:px-6 sm:pt-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow truncate">{siteName ?? session?.tenant?.name}</p>
          <h1 className="display mt-1 flex items-center gap-3 text-[28px] sm:text-[32px]">
            Live
            {list.length > 0 && (
              <span className="rounded-full bg-surface-2 px-2.5 py-0.5 font-[family-name:var(--font-sans)] text-[13px] font-medium tracking-normal text-muted tabular">
                {list.filter((c) => c.enabled).length} cameras
              </span>
            )}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {pages > 1 && (
            <div className="flex items-center gap-1 text-[13px] text-muted tabular">
              <IconButton label="Previous page" size="sm" onClick={() => setPage((current - 1 + pages) % pages)}>
                <ChevronLeft aria-hidden className="size-4" />
              </IconButton>
              {current + 1} / {pages}
              <IconButton label="Next page" size="sm" onClick={() => setPage((current + 1) % pages)}>
                <ChevronRight aria-hidden className="size-4" />
              </IconButton>
            </div>
          )}
          <Segmented<"1" | "4" | "9">
            label="Grid layout"
            value={String(size) as "1" | "4" | "9"}
            onChange={(k) => {
              update({ grid: Number(k) as GridSize });
              setPage(0);
            }}
            items={[
              { key: "1", label: <Square aria-hidden className="size-4" />, title: "Single camera" },
              { key: "4", label: <Grid2x2 aria-hidden className="size-4" />, title: "2 × 2 grid" },
              { key: "9", label: <Grid3x3 aria-hidden className="size-4" />, title: "3 × 3 grid" },
            ]}
          />
        </div>
      </div>

      <div className="mt-5 sm:mt-6">
        {isLoading ? (
          <div className={cn("grid gap-2.5 sm:gap-3", GRID_CLASS[size])}>
            {Array.from({ length: Math.min(size, 4) }, (_, i) => (
              <div key={i} className="skeleton aspect-video rounded-[14px]" />
            ))}
          </div>
        ) : list.length === 0 ? (
          <EmptyState
            icon={Cctv}
            title="No cameras to show"
            action={
              can("cameras:manage") ? (
                <Link to="/cameras">
                  <Button variant="cta">Add a camera</Button>
                </Link>
              ) : undefined
            }
          >
            {can("cameras:manage") ? "Add your first camera to start watching." : "Ask an admin of your organisation to give you access to cameras."}
          </EmptyState>
        ) : (
          <div className={cn("mx-auto grid gap-2.5 sm:gap-3", GRID_CLASS[size])}>
            {visible.map((camera, i) => (
              <CameraTile key={camera.id} camera={camera} paused={maxIndex !== null} onMaximise={() => setMaxIndex(current * size + i)} />
            ))}
          </div>
        )}
      </div>

      {maxIndex !== null && <MaximisedView cameras={list} index={maxIndex} onIndex={setMaxIndex} onClose={() => setMaxIndex(null)} />}
    </div>
  );
}
