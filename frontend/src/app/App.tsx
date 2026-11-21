import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router";

import { ForcedPasswordChangePage, PasswordPage } from "@/features/auth/ChangePasswordPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProfilePage } from "@/features/auth/ProfilePage";
import { SessionsPage } from "@/features/auth/SessionsPage";
import { TotpSetupPage } from "@/features/auth/TotpSetupPage";
import { CatalogsPage } from "@/features/admin/catalogs/CatalogsPage";
import { GroupDetailPage } from "@/features/admin/groups/GroupDetailPage";
import { GroupsPage } from "@/features/admin/groups/GroupsPage";
import { OverviewPage } from "@/features/admin/OverviewPage";
import { RequestsPage } from "@/features/admin/schedule/RequestsPage";
import { SchedulePage as AdminSchedulePage } from "@/features/admin/schedule/SchedulePage";
import { UserCreatePage } from "@/features/admin/users/UserCreatePage";
import { UserDetailPage } from "@/features/admin/users/UserDetailPage";
import { UsersPage } from "@/features/admin/users/UsersPage";
import { JournalPage } from "@/features/journal/JournalPage";
import { LessonPage } from "@/features/journal/LessonPage";
import { AttendancePage } from "@/features/student/AttendancePage";
import { DiaryPage } from "@/features/student/DiaryPage";
import { GradesPage } from "@/features/student/GradesPage";
import { HomePage as StudentHomePage } from "@/features/student/HomePage";
import { TestsPage } from "@/features/student/TestsPage";
import { SchedulePage as StudentSchedulePage } from "@/features/student/SchedulePage";
import { SchedulePage as TeacherSchedulePage } from "@/features/teacher/SchedulePage";
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
      { path: "groups", Component: GroupsPage },
      { path: "groups/:id", Component: GroupDetailPage },
      { path: "schedule", Component: AdminSchedulePage },
      { path: "requests", Component: RequestsPage },
      { path: "catalogs", Component: CatalogsPage },
      { path: "journal", Component: JournalPage },
      { path: "journal/lessons/:id", Component: LessonPage },
    ],
  },
  {
    path: "/teacher",
    element: <Gate section="teacher" />,
    children: [
      { index: true, Component: TodayPage },
      { path: "schedule", Component: TeacherSchedulePage },
      { path: "journal", Component: JournalPage },
      { path: "journal/lessons/:id", Component: LessonPage },
    ],
  },
  {
    path: "/student",
    element: <Gate section="student" />,
    children: [
      { index: true, Component: StudentHomePage },
      { path: "diary", Component: DiaryPage },
      { path: "grades", Component: GradesPage },
      { path: "tests", Component: TestsPage },
      { path: "attendance", Component: AttendancePage },
      { path: "schedule", Component: StudentSchedulePage },
    ],
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
