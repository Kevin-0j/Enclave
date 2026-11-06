import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { SelectField, TextField } from "@/components/ui/Field";
import { ApiError } from "@/lib/api";
import { useSaveCamera, useSites, type CameraInput } from "@/lib/queries";
import type { Camera } from "@/lib/types";

/** Add or edit a camera. Stream addresses are write-only: the API never sends them back, so editing
 *  shows empty fields that keep the stored value unless something is typed. */
export function CameraDialog({ camera, onClose }: { camera: Camera | null; onClose: () => void }) {
  const editing = camera !== null;
  const managed = editing && camera.source_type !== "rtsp";
  const { data: sites } = useSites();
  const save = useSaveCamera();
  const [name, setName] = useState(camera?.name ?? "");
  const [siteId, setSiteId] = useState(camera?.site_id ?? sites?.[0]?.id ?? "");
  const [mainUrl, setMainUrl] = useState("");
  const [subUrl, setSubUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const body: CameraInput = { name, site_id: siteId || null };
    if (mainUrl) body.main_url = mainUrl;
    if (subUrl) body.sub_url = subUrl;
    try {
      await save.mutateAsync({ id: camera?.id, body });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? (err.problem?.errors?.[0]?.msg ?? err.message) : "Couldn't save the camera.");
    }
  };

  return (
    <Dialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={editing ? `Edit ${camera.name}` : "Add a camera"}
      description={editing ? undefined : "Any ONVIF or RTSP camera. Cameras on a private network join through an Enclave gateway."}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="camera-form" variant="cta" loading={save.isPending} disabled={!name || (!editing && !mainUrl)}>
            {editing ? "Save changes" : "Add camera"}
          </Button>
        </>
      }
    >
      <form id="camera-form" onSubmit={submit} className="flex flex-col gap-4" autoComplete="off">
        <TextField label="Name" placeholder="Main gate" required value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
        <SelectField label="Site" value={siteId} onChange={(e) => setSiteId(e.target.value)}>
          <option value="">No site</option>
          {sites?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </SelectField>
        {managed ? (
          <p className="rounded-[10px] bg-surface-2 px-3 py-2.5 text-[13px] text-muted">
            This is a simulated camera. Its stream is managed by Enclave.
          </p>
        ) : (
          <>
            <TextField
              label="Main stream address"
              placeholder={editing ? "Stored securely. Type to replace." : "rtsp://user:password@camera.example.com:554/stream1"}
              value={mainUrl}
              onChange={(e) => setMainUrl(e.target.value)}
              spellCheck={false}
              className="font-[family-name:var(--font-mono)]"
              hint="Encrypted when saved. Enclave never shows it again, to anyone."
            />
            <TextField
              label="Sub-stream address (optional)"
              placeholder={editing ? "Stored securely. Type to replace." : "rtsp://…/stream2"}
              value={subUrl}
              onChange={(e) => setSubUrl(e.target.value)}
              spellCheck={false}
              hint="A lower-resolution stream for grids and phones. Saves bandwidth."
            />
          </>
        )}
        {error && (
          <p role="alert" className="rounded-[10px] bg-danger-soft px-3 py-2.5 text-[13.5px] text-danger">
            {error}
          </p>
        )}
      </form>
    </Dialog>
  );
}
