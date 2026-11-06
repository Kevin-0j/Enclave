import * as RD from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { IconButton } from "./Button";

/** Centred dialog on desktop, bottom sheet on phones (thumb reach). */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <RD.Root open={open} onOpenChange={onOpenChange}>
      <RD.Portal>
        <RD.Overlay className="fixed inset-0 z-50 bg-black/55 backdrop-blur-[2px]" />
        <RD.Content
          aria-describedby={description ? undefined : undefined}
          className={cn(
            "pop-in fixed inset-x-0 bottom-0 z-50 flex max-h-[92dvh] flex-col rounded-t-[var(--radius-sheet)] border border-border bg-surface pb-[env(safe-area-inset-bottom)] shadow-float sm:inset-auto sm:top-1/2 sm:left-1/2 sm:w-[min(520px,calc(100vw-32px))] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[var(--radius-sheet)] sm:pb-0",
            className,
          )}
        >
          <div className="flex items-start gap-3 px-5 pt-5 pb-3">
            <div className="min-w-0 flex-1">
              <RD.Title className="text-[17px] font-semibold">{title}</RD.Title>
              {description && <RD.Description className="mt-1 text-[13.5px] text-muted">{description}</RD.Description>}
            </div>
            <RD.Close asChild>
              <IconButton label="Close" size="sm" className="-mt-1 -mr-1">
                <X aria-hidden className="size-4" />
              </IconButton>
            </RD.Close>
          </div>
          <div className="overflow-y-auto px-5 pb-4">{children}</div>
          {footer && <div className="flex justify-end gap-2 border-t border-border px-5 py-3.5">{footer}</div>}
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}
