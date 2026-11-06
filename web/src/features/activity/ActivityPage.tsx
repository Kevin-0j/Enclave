import { Eye, History, KeyRound, LogIn, Settings2, ShieldAlert, type LucideIcon } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth";
import { actionLabel, relativeTime } from "@/lib/labels";
import { useAudit, useCameras, useMembers } from "@/lib/queries";

function iconFor(action: string): LucideIcon {
  if (action === "live.view") return Eye;
  if (action === "auth.login_failed" || action === "auth.refresh_reuse") return ShieldAlert;
  if (action.startsWith("auth.")) return action === "auth.login" ? LogIn : KeyRound;
  return Settings2;
}

/** The tenant's append-only audit trail: who watched what, and who changed what. */
export function ActivityPage() {
  const { session } = useAuth();
  const { data: rows, isLoading } = useAudit();
  const { data: members } = useMembers();
  const { data: cameras } = useCameras();
  const who = (id: string | null) => members?.find((m) => m.user_id === id)?.email ?? (id ? "Former member" : "Unknown");
  const what = (type: string | null, id: string | null) => (type === "camera" ? cameras?.find((c) => c.id === id)?.name : undefined);

  return (
    <div className="mx-auto max-w-[980px] px-4 pt-5 sm:px-6 sm:pt-7">
      <PageHeader eyebrow={session?.tenant?.name} title="Activity">
        Every sign-in, live view and change, kept as an append-only record.
      </PageHeader>
      <div className="mt-6">
        {isLoading ? (
          <div className="card h-60 skeleton" />
        ) : !rows?.length ? (
          <EmptyState icon={History} title="No activity yet" />
        ) : (
          <ol className="card divide-y divide-border">
            {rows.map((r) => {
              const Icon = iconFor(r.action);
              const target = what(r.target_type, r.target_id);
              const variant = typeof r.detail.variant === "string" ? r.detail.variant : null;
              return (
                <li key={r.id} className="flex items-start gap-3 px-4 py-3 sm:px-5">
                  <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ${r.action === "auth.login_failed" ? "bg-danger-soft text-danger" : "bg-surface-2 text-muted"}`}>
                    <Icon aria-hidden className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13.5px]">
                      <span className="font-medium">{who(r.user_id)}</span> <span className="text-muted">{actionLabel(r.action).toLowerCase()}</span>
                      {target && <span className="font-medium"> {target}</span>}
                      {variant && <span className="text-muted"> ({variant === "main" ? "full quality" : "grid"})</span>}
                    </p>
                    <p className="text-[12px] text-subtle">
                      <time dateTime={r.at} title={new Date(r.at).toLocaleString()}>
                        {relativeTime(r.at)}
                      </time>
                      {r.ip && <span className="font-[family-name:var(--font-mono)]"> · {r.ip}</span>}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}
