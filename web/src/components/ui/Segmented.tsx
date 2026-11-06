import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface SegmentItem<K extends string> {
  key: K;
  label: ReactNode;
  title?: string;
}

/** Accessible radio-style toggle group (arrow keys, Home/End). */
export function Segmented<K extends string>({
  items,
  value,
  onChange,
  label,
  className,
}: {
  items: SegmentItem<K>[];
  value: K;
  onChange: (k: K) => void;
  label: string;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    let next = -1;
    if (e.key === "ArrowRight") next = (i + 1) % items.length;
    if (e.key === "ArrowLeft") next = (i - 1 + items.length) % items.length;
    if (e.key === "Home") next = 0;
    if (e.key === "End") next = items.length - 1;
    const item = items[next];
    if (item) {
      e.preventDefault();
      onChange(item.key);
      refs.current[next]?.focus();
    }
  };
  return (
    <div role="radiogroup" aria-label={label} className={cn("inline-flex rounded-full border border-border bg-surface-2 p-1", className)}>
      {items.map((item, i) => {
        const selected = item.key === value;
        return (
          <button
            key={item.key}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            title={item.title}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.key)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium whitespace-nowrap transition-colors",
              selected ? "bg-surface text-fg shadow-[0_1px_2px_rgb(0_0_0/0.12),0_0_0_1px_var(--border)]" : "text-muted hover:text-fg",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
