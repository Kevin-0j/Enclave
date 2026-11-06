import { Cctv, MoreHorizontal, Pencil, Plus, Power, Trash2 } from "lucide-react";
import * as DM from "@radix-ui/react-dropdown-menu";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button, IconButton } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";
import { relativeTime } from "@/lib/labels";
import { useCameras, useDeleteCamera, useSaveCamera, useSites } from "@/lib/queries";
import type { Camera } from "@/lib/types";
import { CameraDialog } from "./CameraDialog";

const SOURCE: Record<Camera["source_type"], string> = { sim: "Simulated", rtsp: "RTSP", gateway: "Gateway" };

function StatusCell({ camera }: { camera: Camera }) {
  if (!camera.enabled) return <Badge tone="muted" dot>Disabled</Badge>;
  if (camera.status === "online") return <Badge tone="success" dot>Online</Badge>;
  if (camera.status === "offline") return <Badge tone="danger" dot>Offline</Badge>;
  return <Badge tone="muted" dot>Not checked yet</Badge>;
}

export function CamerasPage() {
  const { can } = useAuth();
  const manage = can("cameras:manage");
  const { data: cameras, isLoading } = useCameras();
  const { data: sites } = useSites();
  const save = useSaveCamera();
  const del = useDeleteCamera();
  const [editing, setEditing] = useState<Camera | "new" | null>(null);
  const [deleting, setDeleting] = useState<Camera | null>(null);
  const siteName = (id: string | null) => sites?.find((s) => s.id === id)?.name ?? "—";

  return (
    <div className="mx-auto max-w-[1180px] px-4 pt-5 sm:px-6 sm:pt-7">
      <PageHeader
        eyebrow="Configuration"
        title="Cameras"
        actions={
          manage && (
            <Button variant="cta" icon={<Plus aria-hidden className="size-4" />} onClick={() => setEditing("new")}>
              Add camera
            </Button>
          )
        }
      >
        Health checks (online, last seen, bitrate) arrive with the next release.
      </PageHeader>

      <div className="mt-6">
        {isLoading ? (
          <div className="card flex flex-col gap-3 p-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton h-12" />
            ))}
          </div>
        ) : !cameras?.length ? (
          <EmptyState icon={Cctv} title="No cameras yet" action={manage && <Button variant="cta" onClick={() => setEditing("new")}>Add camera</Button>}>
            Add an RTSP camera, or connect a site through an Enclave gateway.
          </EmptyState>
        ) : (
          <ul className="card divide-y divide-border overflow-hidden">
            {cameras.map((c) => (
              <li key={c.id} className="flex items-center gap-3 px-4 py-3.5 sm:gap-4 sm:px-5">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface-2 text-muted">
                  <Cctv aria-hidden className="size-[18px]" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{c.name}</p>
                  <p className="truncate text-[12.5px] text-muted">
                    {siteName(c.site_id)} · {SOURCE[c.source_type]}
                    {c.last_seen && ` · seen ${relativeTime(c.last_seen)}`}
                  </p>
                </div>
                <div className="hidden sm:block">
                  <StatusCell camera={c} />
                </div>
                {manage && (
                  <DM.Root>
                    <DM.Trigger asChild>
                      <IconButton label={`Actions for ${c.name}`} size="sm">
                        <MoreHorizontal aria-hidden className="size-4" />
                      </IconButton>
                    </DM.Trigger>
                    <DM.Portal>
                      <DM.Content align="end" sideOffset={6} className="pop-in z-50 min-w-48 rounded-2xl border border-border bg-surface p-1.5 shadow-float">
                        <DM.Item onSelect={() => setEditing(c)} className="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 outline-none data-[highlighted]:bg-surface-2">
                          <Pencil aria-hidden className="size-4" /> Edit
                        </DM.Item>
                        <DM.Item
                          onSelect={() => save.mutate({ id: c.id, body: { enabled: !c.enabled } })}
                          className="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 outline-none data-[highlighted]:bg-surface-2"
                        >
                          <Power aria-hidden className="size-4" /> {c.enabled ? "Disable" : "Enable"}
                        </DM.Item>
                        <DM.Separator className="my-1 h-px bg-border" />
                        <DM.Item onSelect={() => setDeleting(c)} className="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-danger outline-none data-[highlighted]:bg-danger-soft">
                          <Trash2 aria-hidden className="size-4" /> Remove
                        </DM.Item>
                      </DM.Content>
                    </DM.Portal>
                  </DM.Root>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {editing && <CameraDialog camera={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {deleting && (
        <Dialog
          open
          onOpenChange={(o) => !o && setDeleting(null)}
          title={`Remove ${deleting.name}?`}
          description="Live view stops for everyone. This is recorded in the activity log."
          footer={
            <>
              <Button variant="ghost" onClick={() => setDeleting(null)}>
                Cancel
              </Button>
              <Button variant="danger" loading={del.isPending} onClick={() => del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}>
                Remove camera
              </Button>
            </>
          }
        >
          <span />
        </Dialog>
      )}
    </div>
  );
}
