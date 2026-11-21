import { lazy, Suspense } from "react";
import { Navigate, Outlet } from "react-router";

import { homePath, useMe, type Role } from "@/features/auth/api";
import { errorMessage } from "@/shared/api/errors";
import { RuledSkeleton } from "@/shared/ui/RuledSkeleton";

import { OfflinePage } from "./OfflinePage";

import { NotFoundPage } from "./NotFoundPage";

// The shell and its menus/dialogs are not needed on the login page (SPEC §15).
const Shell = lazy(() => import("./Shell").then((m) => ({ default: m.Shell })));
const ReauthOutlet = lazy(() => import("./Shell").then((m) => ({ default: m.ReauthOutlet })));

type GateProps = {
  /** Section of one role; another role sees 404 (the server would answer 403 anyway). */
  section?: Role;
  /** Full-screen forced steps: temporary password, 2FA setup. */
  mode?: "password" | "totp";
};

/**
 * Client-side routing only. Every rule here is also enforced by the server (SPEC §11);
 * this just shows the right screen.
 */
export function Gate({ section, mode }: GateProps) {
  const me = useMe();
  if (me.isPending) return <RuledSkeleton />;
  // Offline the shell still opens (service worker), but there is no data: say so.
  if (me.error instanceof TypeError) return <OfflinePage onRetry={() => void me.refetch()} />;
  if (me.error) return <p role="alert">{errorMessage(me.error)}</p>;
  const user = me.data;
  if (!user) return <Navigate to="/login" replace />;

  if (user.must_change_password) {
    return mode === "password" ? <Outlet /> : <Navigate to="/change-password" replace />;
  }
  if (mode === "password") return <Navigate to="/" replace />;
  if (mode === "totp")
    return (
      <Suspense fallback={<RuledSkeleton />}>
        <ReauthOutlet />
      </Suspense>
    );
  if (user.totp_setup_required) return <Navigate to="/setup-2fa" replace />;
  if (section && user.active_role !== section) return <NotFoundPage />;

  return (
    <Suspense fallback={<RuledSkeleton />}>
      <Shell me={user} />
    </Suspense>
  );
}

export function RootRedirect() {
  const me = useMe();
  if (me.isPending) return <RuledSkeleton />;
  if (!me.data) return <Navigate to="/login" replace />;
  return <Navigate to={homePath(me.data.active_role)} replace />;
}
