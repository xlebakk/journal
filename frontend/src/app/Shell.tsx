import { Outlet } from "react-router";

import type { Me } from "@/features/auth/api";
import { ReauthProvider } from "@/features/auth/reauth";

import { AppShell } from "./AppShell";

/** Everything a logged-in screen needs around it; loaded after login (see Gate). */
export function Shell({ me }: { me: Me }) {
  return (
    <ReauthProvider>
      <AppShell me={me} />
    </ReauthProvider>
  );
}

export function ReauthOutlet() {
  return (
    <ReauthProvider>
      <Outlet />
    </ReauthProvider>
  );
}
