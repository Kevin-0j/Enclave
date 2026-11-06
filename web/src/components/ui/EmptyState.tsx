import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({ icon: Icon, title, children, action }: { icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center px-6 py-14 text-center">
      <span className="grid size-12 place-items-center rounded-2xl bg-surface-2 text-muted">
        <Icon aria-hidden className="size-5" />
      </span>
      <h2 className="mt-4 text-[16px] font-semibold">{title}</h2>
      {children && <p className="mt-1.5 max-w-sm text-[13.5px] text-muted">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
