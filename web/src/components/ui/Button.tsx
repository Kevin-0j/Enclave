import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "cta" | "secondary" | "ghost" | "danger" | "danger-ghost" | "overlay";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

const variants: Record<Variant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover shadow-1",
  /** The one amber action per screen. */
  cta: "bg-amber text-ink-on-amber hover:bg-amber-2 shadow-[inset_0_-1px_0_rgb(0_0_0/0.14)]",
  secondary: "bg-surface text-fg border border-border hover:border-border-strong hover:bg-surface-2",
  ghost: "text-fg hover:bg-surface-2",
  danger: "bg-danger text-white hover:opacity-90 shadow-1 dark:text-bg",
  "danger-ghost": "text-danger hover:bg-danger-soft",
  /** On top of video. */
  overlay: "bg-black/45 text-white backdrop-blur-md hover:bg-black/65 ring-1 ring-white/10",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-[9px]",
  md: "h-10 px-4 text-sm gap-2 rounded-[10px]",
  lg: "h-12 px-6 text-[15px] gap-2 rounded-full",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading = false, icon, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center font-medium whitespace-nowrap transition-[background-color,border-color,color,transform] duration-150 select-none active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 disabled:saturate-50 disabled:active:scale-100",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 aria-hidden className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

export const IconButton = forwardRef<HTMLButtonElement, ButtonProps & { label: string }>(function IconButton(
  { label, className, size = "md", variant = "ghost", ...rest },
  ref,
) {
  return (
    <Button
      ref={ref}
      aria-label={label}
      title={label}
      variant={variant}
      size={size}
      className={cn(size === "sm" ? "w-8 px-0" : size === "lg" ? "w-12 px-0" : "w-10 px-0", className)}
      {...rest}
    />
  );
});
