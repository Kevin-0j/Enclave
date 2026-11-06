import { ArrowRight, Fingerprint, Lock, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { LogoMark, Logo } from "@/components/layout/Logo";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  { email: "admin@mlima.demo", label: "Mlima Residences", role: "Admin" },
  { email: "viewer@mlima.demo", label: "Mlima Residences", role: "Viewer" },
  { email: "admin@ngong.demo", label: "Ngong Road Offices", role: "Admin" },
];

export function LoginPage() {
  const { session, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const from = (location.state as { from?: string } | null)?.from ?? "/live";

  if (session) return <Navigate to={from} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Can't reach Enclave. Check your connection.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <Hero />
      <div className="flex flex-col px-5 pt-[max(2rem,env(safe-area-inset-top))] pb-8 sm:px-10">
        <div className="lg:hidden">
          <Logo />
        </div>
        <div className="mx-auto flex w-full max-w-[380px] flex-1 flex-col justify-center py-10">
          <p className="eyebrow">Sign in</p>
          <h1 className="display mt-2 text-[34px]">Welcome back</h1>
          <p className="mt-2 text-[14px] text-muted">Watch every site you look after from one place.</p>

          <form onSubmit={submit} className="mt-8 flex flex-col gap-4" noValidate>
            <TextField
              label="Email"
              type="email"
              autoComplete="username"
              inputMode="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <TextField
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && (
              <p role="alert" className="rounded-[10px] bg-danger-soft px-3 py-2.5 text-[13.5px] text-danger">
                {error}
              </p>
            )}
            <Button type="submit" variant="cta" size="lg" loading={busy} className="mt-2 w-full" disabled={!email || !password}>
              Sign in <ArrowRight aria-hidden className="size-4" />
            </Button>
          </form>

          {import.meta.env.DEV && (
            <div className="mt-8 rounded-[var(--radius-card)] border border-dashed border-border-strong p-4">
              <p className="eyebrow">Demo accounts</p>
              <p className="mt-1 text-[12.5px] text-muted">Password is SEED_PASSWORD in your .env.</p>
              <ul className="mt-3 flex flex-col gap-1">
                {DEMO_ACCOUNTS.map((a) => (
                  <li key={a.email}>
                    <button
                      type="button"
                      onClick={() => setEmail(a.email)}
                      className="flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left text-[13px] hover:bg-surface-2"
                    >
                      <span className="truncate font-[family-name:var(--font-mono)] text-[12.5px]">{a.email}</span>
                      <span className="shrink-0 text-muted">{a.role}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <p className="text-center text-[12px] text-subtle">
          Video stays isolated per organisation. Every view is logged.
        </p>
      </div>
    </div>
  );
}

/** Desktop-only brand panel: a quiet monitor wall, not stock photography. */
function Hero() {
  const tiles = ["Main gate", "Visitor parking", "Block A lobby", "North perimeter", "Reception", "Loading bay"];
  return (
    <div className="grain relative hidden overflow-hidden bg-ink text-white lg:flex lg:flex-col">
      <div className="wall-grid absolute inset-0 opacity-60" />
      <div className="relative flex flex-1 flex-col p-10 xl:p-14">
        <div className="flex items-center gap-2.5">
          <LogoMark className="size-8" />
          <span className="font-[family-name:var(--font-display)] text-[21px] font-medium tracking-[-0.02em]">Enclave</span>
        </div>
        <div className="mt-auto max-w-xl">
          <h2 className="display text-[52px] xl:text-[60px]">
            Every site.
            <br />
            <span className="text-amber">One calm screen.</span>
          </h2>
          <p className="mt-5 max-w-md text-[15px] leading-relaxed text-white/70">
            Live view, recordings and alerts for any ONVIF or RTSP camera, across every property you manage. Hosted in Kenya.
          </p>
        </div>
        <div className="mt-10 grid grid-cols-3 gap-2.5" aria-hidden>
          {tiles.map((t, i) => (
            <div key={t} className="relative aspect-video overflow-hidden rounded-xl bg-[#0a1520] ring-1 ring-white/10">
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,rgb(255_255_255/0.07),transparent_60%)]" />
              <div className="absolute inset-x-0 bottom-0 h-1/3 bg-[#13202c]" />
              <span className="absolute top-2 left-2 flex items-center gap-1.5 rounded-md bg-black/40 px-1.5 py-0.5 text-[10px] text-white/80">
                <span className={`size-1.5 rounded-full ${i === 0 ? "pulse-dot bg-live text-live" : "bg-success"}`} />
                {t}
              </span>
            </div>
          ))}
        </div>
        <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[13px] text-white/65">
          <li className="flex items-center gap-2">
            <ShieldCheck aria-hidden className="size-4 text-amber" /> Tenant isolation in the database
          </li>
          <li className="flex items-center gap-2">
            <Lock aria-hidden className="size-4 text-amber" /> No open ports at your sites
          </li>
          <li className="flex items-center gap-2">
            <Fingerprint aria-hidden className="size-4 text-amber" /> Full audit trail for the KDPA
          </li>
        </ul>
      </div>
    </div>
  );
}
