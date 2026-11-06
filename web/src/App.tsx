import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { LogoMark } from "@/components/layout/Logo";
import { ActivityPage } from "@/features/activity/ActivityPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { CamerasPage } from "@/features/cameras/CamerasPage";
import { LivePage } from "@/features/live/LivePage";
import { PeoplePage } from "@/features/people/PeoplePage";
import { useAuth } from "@/lib/auth";

function Splash() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <span className="flex items-center gap-3 text-muted" role="status">
        <LogoMark className="size-8" />
        <Loader2 aria-hidden className="size-4 animate-spin" />
        <span className="sr-only">Loading Enclave</span>
      </span>
    </div>
  );
}

function Protected({ children }: { children: ReactNode }) {
  const { session, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <Splash />;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function Gate({ perm, children }: { perm: string; children: ReactNode }) {
  const { can } = useAuth();
  return can(perm) ? <>{children}</> : <Navigate to="/live" replace />;
}

function NoTenant() {
  const { session, signOut } = useAuth();
  return (
    <div className="mx-auto max-w-md px-6 py-24 text-center">
      <h1 className="display text-[28px]">No organisation selected</h1>
      <p className="mt-3 text-muted">
        {session?.user.is_platform_admin
          ? "Platform admins manage tenants through the API for now. Tenant data stays closed to you unless you're a member."
          : "You're not a member of any organisation yet."}
      </p>
      <button type="button" className="mt-6 text-[14px] text-accent underline" onClick={() => void signOut()}>
        Sign out
      </button>
    </div>
  );
}

export function App() {
  const { ready, session } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={ready ? <LoginPage /> : <Splash />} />
      <Route
        element={
          <Protected>
            <AppShell />
          </Protected>
        }
      >
        {session && !session.tenant ? (
          <Route path="*" element={<NoTenant />} />
        ) : (
          <>
            <Route path="/live" element={<Gate perm="live:view"><LivePage /></Gate>} />
            <Route path="/cameras" element={<Gate perm="cameras:read"><CamerasPage /></Gate>} />
            <Route path="/people" element={<Gate perm="users:read"><PeoplePage /></Gate>} />
            <Route path="/activity" element={<Gate perm="audit:read"><ActivityPage /></Gate>} />
            <Route path="*" element={<Navigate to="/live" replace />} />
          </>
        )}
      </Route>
    </Routes>
  );
}
