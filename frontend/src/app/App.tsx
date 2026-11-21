import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router";

import { ForcedPasswordChangePage, PasswordPage } from "@/features/auth/ChangePasswordPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProfilePage } from "@/features/auth/ProfilePage";
import { SessionsPage } from "@/features/auth/SessionsPage";
import { TotpSetupPage } from "@/features/auth/TotpSetupPage";
import { OverviewPage } from "@/features/admin/OverviewPage";
import { UserCreatePage } from "@/features/admin/users/UserCreatePage";
import { UserDetailPage } from "@/features/admin/users/UserDetailPage";
import { UsersPage } from "@/features/admin/users/UsersPage";
import { HomePage as StudentHomePage } from "@/features/student/HomePage";
import { TodayPage } from "@/features/teacher/TodayPage";
import { RuledSkeleton } from "@/shared/ui";

import { Gate, RootRedirect } from "./Gate";
import { NotFoundPage } from "./NotFoundPage";
import { createQueryClient } from "./queryClient";

const queryClient = createQueryClient();

// import.meta.env.DEV is a build-time constant: the styleguide is not in the production bundle.
const devRoutes: RouteObject[] = import.meta.env.DEV
  ? [{ path: "/dev/styleguide", Component: lazy(() => import("@/dev/StyleguidePage")) }]
  : [];

const routes: RouteObject[] = [
  { path: "/", Component: RootRedirect },
  { path: "/login", Component: LoginPage },
  {
    element: <Gate mode="password" />,
    children: [{ path: "/change-password", Component: ForcedPasswordChangePage }],
  },
  {
    element: <Gate mode="totp" />,
    children: [{ path: "/setup-2fa", Component: TotpSetupPage }],
  },
  {
    path: "/admin",
    element: <Gate section="admin" />,
    children: [
      { index: true, Component: OverviewPage },
      { path: "users", Component: UsersPage },
      { path: "users/new", Component: UserCreatePage },
      { path: "users/:id", Component: UserDetailPage },
    ],
  },
  {
    path: "/teacher",
    element: <Gate section="teacher" />,
    children: [{ index: true, Component: TodayPage }],
  },
  {
    path: "/student",
    element: <Gate section="student" />,
    children: [{ index: true, Component: StudentHomePage }],
  },
  {
    path: "/account",
    element: <Gate />,
    children: [
      { path: "profile", Component: ProfilePage },
      { path: "password", Component: PasswordPage },
      { path: "sessions", Component: SessionsPage },
    ],
  },
  ...devRoutes,
  { path: "*", Component: NotFoundPage },
];

const router = createBrowserRouter(routes);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<RuledSkeleton />}>
        <RouterProvider router={router} />
      </Suspense>
    </QueryClientProvider>
  );
}
