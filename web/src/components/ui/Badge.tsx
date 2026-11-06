import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type Tone = "success" | "info" | "warning" | "danger" | "muted" | "live" | "accent";

const TONES: Record<Tone, string> = {
  success: "bg-success-soft text-success",
  info: "bg-info-soft text-info",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  muted: "bg-surface-2 text-muted",
  live: "bg-live-soft text-live",
  accent: "bg-amber-soft text-warning dark:text-amber",
};

/** Status is always icon or dot + text + colour, never colour alone. */
export function Badge({ tone, children, dot, className }: { tone: Tone; children: ReactNode; dot?: boolean; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12.5px] font-medium whitespace-nowrap ring-1 ring-current/10 ring-inset",
        TONES[tone],
        className,
      )}
    >
      {dot && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
