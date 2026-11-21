import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router";

import { ForcedPasswordChangePage, PasswordPage } from "@/features/auth/ChangePasswordPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProfilePage } from "@/features/auth/ProfilePage";
import { SessionsPage } from "@/features/auth/SessionsPage";
import { TotpSetupPage } from "@/features/auth/TotpSetupPage";
import { AuditPage } from "@/features/admin/audit/AuditPage";
import { CatalogsPage } from "@/features/admin/catalogs/CatalogsPage";
import { GroupDetailPage } from "@/features/admin/groups/GroupDetailPage";
import { GroupsPage } from "@/features/admin/groups/GroupsPage";
import { ImportPage } from "@/features/admin/import/ImportPage";
import { OverviewPage } from "@/features/admin/OverviewPage";
import { RequestsPage } from "@/features/admin/schedule/RequestsPage";
import { SchedulePage as AdminSchedulePage } from "@/features/admin/schedule/SchedulePage";
import { SettingsPage } from "@/features/admin/settings/SettingsPage";
import { UserCreatePage } from "@/features/admin/users/UserCreatePage";
import { UserDetailPage } from "@/features/admin/users/UserDetailPage";
import { UsersPage } from "@/features/admin/users/UsersPage";
import { AnnouncementsPage } from "@/features/announcements/AnnouncementsPage";
import { ExamPage } from "@/features/exams/ExamPage";
import { ExamsPage } from "@/features/exams/ExamsPage";
import { JournalPage } from "@/features/journal/JournalPage";
import { LessonPage } from "@/features/journal/LessonPage";
import { AdminReportsPage } from "@/features/reports/AdminReportsPage";
import { TeacherReportsPage } from "@/features/reports/StatementPanel";
import { StudentSummaryPage } from "@/features/reports/StudentSummaryPage";
import { AttendancePage } from "@/features/student/AttendancePage";
import { DiaryPage } from "@/features/student/DiaryPage";
import { GradesPage } from "@/features/student/GradesPage";
import { HomePage as StudentHomePage } from "@/features/student/HomePage";
import { TestsPage } from "@/features/student/TestsPage";
import { SchedulePage as StudentSchedulePage } from "@/features/student/SchedulePage";
import { SchedulePage as TeacherSchedulePage } from "@/features/teacher/SchedulePage";
import { TodayPage } from "@/features/teacher/TodayPage";
import { onBackButton } from "@/platform";
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
      { path: "import", Component: ImportPage },
      { path: "groups", Component: GroupsPage },
      { path: "groups/:id", Component: GroupDetailPage },
      { path: "schedule", Component: AdminSchedulePage },
      { path: "requests", Component: RequestsPage },
      { path: "catalogs", Component: CatalogsPage },
      { path: "journal", Component: JournalPage },
      { path: "journal/lessons/:id", Component: LessonPage },
      { path: "exams", Component: ExamsPage },
      { path: "exams/:id", Component: ExamPage },
      { path: "reports", Component: AdminReportsPage },
      { path: "reports/students/:id", Component: StudentSummaryPage },
      { path: "announcements", Component: AnnouncementsPage },
      { path: "audit", Component: AuditPage },
      { path: "settings", Component: SettingsPage },
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
      { path: "exams", Component: ExamsPage },
      { path: "exams/:id", Component: ExamPage },
      { path: "reports", Component: TeacherReportsPage },
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

/** React Router keeps the position in the history as `idx`. */
function canGoBack(): boolean {
  const state = window.history.state as { idx?: number } | null;
  return (state?.idx ?? 0) > 0;
}

export function App() {
  // The Android «Назад» (no-op on the site).
  useEffect(() => onBackButton(() => void router.navigate(-1), canGoBack), []);
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<RuledSkeleton />}>
        <RouterProvider router={router} />
      </Suspense>
    </QueryClientProvider>
  );
}
