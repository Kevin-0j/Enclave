import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export const inputClass =
  "w-full rounded-[10px] border border-border-strong bg-surface px-3 text-fg placeholder:text-subtle transition-[border-color,box-shadow] hover:border-muted/50 focus-visible:border-accent focus-visible:shadow-[0_0_0_4px_var(--accent-soft)] focus-visible:outline-none aria-[invalid=true]:border-danger";

interface FieldProps {
  label: string;
  error?: string | null;
  hint?: ReactNode;
}

function Messages({ id, error, hint }: { id: string; error?: string | null; hint?: ReactNode }) {
  return (
    <>
      {hint && !error && (
        <p id={`${id}-hint`} className="text-[13px] text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-err`} className="text-[13px] text-danger">
          {error}
        </p>
      )}
    </>
  );
}

export const TextField = forwardRef<HTMLInputElement, FieldProps & InputHTMLAttributes<HTMLInputElement>>(function TextField(
  { label, error, hint, className, id, ...rest },
  ref,
) {
  const auto = useId();
  const fieldId = id ?? auto;
  const describedBy = [error && `${fieldId}-err`, hint && `${fieldId}-hint`].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={fieldId} className="text-[13px] font-medium">
        {label}
      </label>
      <input ref={ref} id={fieldId} aria-invalid={!!error} aria-describedby={describedBy} className={cn(inputClass, "h-11")} {...rest} />
      <Messages id={fieldId} error={error} hint={hint} />
    </div>
  );
});

export const SelectField = forwardRef<HTMLSelectElement, FieldProps & SelectHTMLAttributes<HTMLSelectElement>>(function SelectField(
  { label, error, hint, className, id, children, ...rest },
  ref,
) {
  const auto = useId();
  const fieldId = id ?? auto;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={fieldId} className="text-[13px] font-medium">
        {label}
      </label>
      <select ref={ref} id={fieldId} aria-invalid={!!error} className={cn(inputClass, "h-11 pr-8")} {...rest}>
        {children}
      </select>
      <Messages id={fieldId} error={error} hint={hint} />
    </div>
  );
});
