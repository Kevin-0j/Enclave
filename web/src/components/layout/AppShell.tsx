import * as DM from "@radix-ui/react-dropdown-menu";
import { Building2, Check, ChevronsUpDown, History, LogOut, Moon, Sun, Users, Video, Cctv, type LucideIcon } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { ROLE_LABEL } from "@/lib/labels";
import { useSettings } from "@/lib/settings";
import { Logo } from "./Logo";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  perm: string;
}

const NAV: NavItem[] = [
  { to: "/live", label: "Live", icon: Video, perm: "live:view" },
  { to: "/cameras", label: "Cameras", icon: Cctv, perm: "cameras:read" },
  { to: "/people", label: "People", icon: Users, perm: "users:read" },
  { to: "/activity", label: "Activity", icon: History, perm: "audit:read" },
];

export function useNav(): NavItem[] {
  const { can } = useAuth();
  return NAV.filter((n) => can(n.perm));
}

export function AppShell() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only z-50 rounded bg-surface p-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2">
        Skip to content
      </a>
      <Header />
      <main id="main" className="min-w-0 flex-1 pb-[calc(5rem+env(safe-area-inset-bottom))] md:pb-10">
        <Outlet />
      </main>
      <MobileTabBar />
    </div>
  );
}

function Header() {
  const nav = useNav();
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/85 pt-[env(safe-area-inset-top)] backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1480px] items-center gap-3 px-4 sm:px-6">
        <Link to="/live" aria-label="Enclave home" className="shrink-0 rounded-lg">
          <Logo />
        </Link>
        <nav aria-label="Main" className="ml-4 hidden items-center gap-0.5 md:flex">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                cn(
                  "inline-flex h-9 items-center gap-2 rounded-full px-3.5 text-[13.5px] font-medium transition-colors",
                  isActive ? "bg-surface text-fg shadow-[0_0_0_1px_var(--border)]" : "text-muted hover:text-fg",
                )
              }
            >
              <n.icon aria-hidden className="size-4" />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
          <TenantSwitcher />
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}

function TenantSwitcher() {
  const { session, switchTenant } = useAuth();
  if (!session?.tenant) return null;
  const many = session.memberships.length > 1;
  const label = (
    <>
      <Building2 aria-hidden className="size-4 shrink-0 text-muted" />
      <span className="max-w-[9rem] truncate sm:max-w-[14rem]">{session.tenant.name}</span>
      {many && <ChevronsUpDown aria-hidden className="size-3.5 text-subtle" />}
    </>
  );
  const pill = "inline-flex h-9 items-center gap-2 rounded-full border border-border bg-surface px-3 text-[13px] font-medium";
  if (!many) return <span className={pill}>{label}</span>;
  return (
    <DM.Root>
      <DM.Trigger className={cn(pill, "hover:border-border-strong")} aria-label={`Organisation: ${session.tenant.name}. Switch`}>
        {label}
      </DM.Trigger>
      <DM.Portal>
        <DM.Content align="end" sideOffset={8} className="pop-in z-50 min-w-64 rounded-2xl border border-border bg-surface p-1.5 shadow-float">
          <DM.Label className="px-2.5 py-2 text-xs text-muted">Organisations</DM.Label>
          {session.memberships.map((m) => (
            <DM.Item
              key={m.tenant.id}
              onSelect={() => void switchTenant(m.tenant.id)}
              className="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 outline-none data-[highlighted]:bg-surface-2"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate">{m.tenant.name}</span>
                <span className="text-xs text-muted">{ROLE_LABEL[m.role]}</span>
              </span>
              {m.tenant.id === session.tenant?.id && <Check aria-hidden className="size-4 text-accent" />}
            </DM.Item>
          ))}
        </DM.Content>
      </DM.Portal>
    </DM.Root>
  );
}

function ThemeToggle() {
  const [settings, update] = useSettings();
  const dark = document.documentElement.dataset.theme === "dark";
  return (
    <button
      type="button"
      onClick={() => update({ theme: dark ? "light" : "dark" })}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Light theme" : "Dark theme"}
      data-theme-setting={settings.theme}
      className="grid size-9 place-items-center rounded-full text-muted hover:bg-surface-2 hover:text-fg"
    >
      {dark ? <Sun aria-hidden className="size-[18px]" /> : <Moon aria-hidden className="size-[18px]" />}
    </button>
  );
}

function UserMenu() {
  const { session, signOut } = useAuth();
  const name = session?.user.name || session?.user.email || "";
  return (
    <DM.Root>
      <DM.Trigger className="inline-flex h-9 items-center gap-2 rounded-full border border-border bg-surface p-1 hover:border-border-strong lg:pr-3">
        <span aria-hidden className="grid size-7 place-items-center rounded-full bg-ink text-[12px] font-semibold text-amber">
          {name.slice(0, 1).toUpperCase() || "?"}
        </span>
        <span className="sr-only">Account menu for </span>
        <span className="sr-only max-w-40 truncate text-[13px] font-medium whitespace-nowrap lg:not-sr-only">{name}</span>
      </DM.Trigger>
      <DM.Portal>
        <DM.Content align="end" sideOffset={8} className="pop-in z-50 min-w-60 rounded-2xl border border-border bg-surface p-1.5 shadow-float">
          <div className="px-2.5 py-2">
            <p className="truncate text-[13.5px] font-medium">{name}</p>
            <p className="truncate text-xs text-muted">{session?.user.email}</p>
            {session?.role && <p className="mt-1 text-xs text-muted">{ROLE_LABEL[session.role]}</p>}
          </div>
          <DM.Separator className="my-1 h-px bg-border" />
          <DM.Item
            onSelect={() => void signOut()}
            className="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-danger outline-none data-[highlighted]:bg-danger-soft"
          >
            <LogOut aria-hidden className="size-4" /> Sign out
          </DM.Item>
        </DM.Content>
      </DM.Portal>
    </DM.Root>
  );
}

/** Thumb-reachable bottom tabs under md. */
function MobileTabBar() {
  const nav = useNav();
  return (
    <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden">
      <div className="flex h-16 items-stretch px-1">
        {nav.map((n) => (
          <NavLink key={n.to} to={n.to} className={({ isActive }) => cn("flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium", isActive ? "text-fg" : "text-muted")}>
            {({ isActive }) => (
              <>
                <span className={cn("grid h-7 w-12 place-items-center rounded-full transition-colors", isActive && "bg-surface-3")}>
                  <n.icon aria-hidden className="size-[18px]" />
                </span>
                {n.label}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
