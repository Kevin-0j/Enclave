/** Enclave mark: a lens inside an open enclosure (the wall around a site), amber on navy. */
export function LogoMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 64 64" className={className}>
      <rect width="64" height="64" rx="16" fill="var(--ink)" />
      <path d="M45.5 21.5A17 17 0 1 0 49 32" fill="none" stroke="var(--amber)" strokeWidth="5" strokeLinecap="round" />
      <circle cx="32" cy="32" r="6.5" fill="var(--amber)" />
    </svg>
  );
}

export function Logo({ compact, tone = "default" }: { compact?: boolean; tone?: "default" | "inverse" }) {
  return (
    <span className="inline-flex items-center gap-2">
      <LogoMark />
      {!compact && (
        <span className={`font-[family-name:var(--font-display)] text-[19px] font-medium tracking-[-0.02em] ${tone === "inverse" ? "text-white" : "text-fg"}`}>
          Enclave
        </span>
      )}
    </span>
  );
}
