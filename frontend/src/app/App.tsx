import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, type ComponentType } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router";

import { LoginPage } from "@/features/auth/LoginPage";
import { onBackButton } from "@/platform";
import { RuledSkeleton } from "@/shared/ui";

import { Gate, RootRedirect } from "./Gate";
import { NotFoundPage } from "./NotFoundPage";
import { createQueryClient } from "./queryClient";

const queryClient = createQueryClient();

/**
 * Screens load on first visit (SPEC §15: the login page must stay light — performance ≥ 90 on
 * a phone). React Router fetches the module before rendering the route.
 */
function page<M extends Record<string, unknown>>(load: () => Promise<M>, name: keyof M & string) {
  return async () => ({ Component: (await load())[name] as ComponentType });
}

// import.meta.env.DEV is a build-time constant: the styleguide is not in the production bundle.
const devRoutes: RouteObject[] = import.meta.env.DEV
  ? [{ path: "/dev/styleguide", Component: lazy(() => import("@/dev/StyleguidePage")) }]
  : [];

const routes: RouteObject[] = [
  { path: "/", Component: RootRedirect },
  { path: "/login", Component: LoginPage },
  {
    element: <Gate mode="password" />,
    children: [
      {
        path: "/change-password",
        lazy: page(() => import("@/features/auth/ChangePasswordPage"), "ForcedPasswordChangePage"),
      },
    ],
  },
  {
    element: <Gate mode="totp" />,
    children: [
      {
        path: "/setup-2fa",
        lazy: page(() => import("@/features/auth/TotpSetupPage"), "TotpSetupPage"),
      },
    ],
  },
  {
    path: "/admin",
    element: <Gate section="admin" />,
    children: [
      { index: true, lazy: page(() => import("@/features/admin/OverviewPage"), "OverviewPage") },
      { path: "users", lazy: page(() => import("@/features/admin/users/UsersPage"), "UsersPage") },
      {
        path: "users/new",
        lazy: page(() => import("@/features/admin/users/UserCreatePage"), "UserCreatePage"),
      },
      {
        path: "users/:id",
        lazy: page(() => import("@/features/admin/users/UserDetailPage"), "UserDetailPage"),
      },
      {
        path: "import",
        lazy: page(() => import("@/features/admin/import/ImportPage"), "ImportPage"),
      },
      {
        path: "groups",
        lazy: page(() => import("@/features/admin/groups/GroupsPage"), "GroupsPage"),
      },
      {
        path: "groups/:id",
        lazy: page(() => import("@/features/admin/groups/GroupDetailPage"), "GroupDetailPage"),
      },
      {
        path: "schedule",
        lazy: page(() => import("@/features/admin/schedule/SchedulePage"), "SchedulePage"),
      },
      {
        path: "requests",
        lazy: page(() => import("@/features/admin/schedule/RequestsPage"), "RequestsPage"),
      },
      {
        path: "catalogs",
        lazy: page(() => import("@/features/admin/catalogs/CatalogsPage"), "CatalogsPage"),
      },
      {
        path: "journal",
        lazy: page(() => import("@/features/journal/JournalPage"), "JournalPage"),
      },
      {
        path: "journal/lessons/:id",
        lazy: page(() => import("@/features/journal/LessonPage"), "LessonPage"),
      },
      { path: "exams", lazy: page(() => import("@/features/exams/ExamsPage"), "ExamsPage") },
      { path: "exams/:id", lazy: page(() => import("@/features/exams/ExamPage"), "ExamPage") },
      {
        path: "reports",
        lazy: page(() => import("@/features/reports/AdminReportsPage"), "AdminReportsPage"),
      },
      {
        path: "reports/students/:id",
        lazy: page(() => import("@/features/reports/StudentSummaryPage"), "StudentSummaryPage"),
      },
      {
        path: "announcements",
        lazy: page(() => import("@/features/announcements/AnnouncementsPage"), "AnnouncementsPage"),
      },
      { path: "audit", lazy: page(() => import("@/features/admin/audit/AuditPage"), "AuditPage") },
      {
        path: "settings",
        lazy: page(() => import("@/features/admin/settings/SettingsPage"), "SettingsPage"),
      },
    ],
  },
  {
    path: "/teacher",
    element: <Gate section="teacher" />,
    children: [
      { index: true, lazy: page(() => import("@/features/teacher/TodayPage"), "TodayPage") },
      {
        path: "schedule",
        lazy: page(() => import("@/features/teacher/SchedulePage"), "SchedulePage"),
      },
      {
        path: "journal",
        lazy: page(() => import("@/features/journal/JournalPage"), "JournalPage"),
      },
      {
        path: "journal/lessons/:id",
        lazy: page(() => import("@/features/journal/LessonPage"), "LessonPage"),
      },
      { path: "exams", lazy: page(() => import("@/features/exams/ExamsPage"), "ExamsPage") },
      { path: "exams/:id", lazy: page(() => import("@/features/exams/ExamPage"), "ExamPage") },
      {
        path: "reports",
        lazy: page(() => import("@/features/reports/StatementPanel"), "TeacherReportsPage"),
      },
    ],
  },
  {
    path: "/student",
    element: <Gate section="student" />,
    children: [
      { index: true, lazy: page(() => import("@/features/student/HomePage"), "HomePage") },
      { path: "diary", lazy: page(() => import("@/features/student/DiaryPage"), "DiaryPage") },
      { path: "grades", lazy: page(() => import("@/features/student/GradesPage"), "GradesPage") },
      { path: "tests", lazy: page(() => import("@/features/student/TestsPage"), "TestsPage") },
      {
        path: "attendance",
        lazy: page(() => import("@/features/student/AttendancePage"), "AttendancePage"),
      },
      {
        path: "schedule",
        lazy: page(() => import("@/features/student/SchedulePage"), "SchedulePage"),
      },
    ],
  },
  {
    path: "/account",
    element: <Gate />,
    children: [
      { path: "profile", lazy: page(() => import("@/features/auth/ProfilePage"), "ProfilePage") },
      {
        path: "password",
        lazy: page(() => import("@/features/auth/ChangePasswordPage"), "PasswordPage"),
      },
      {
        path: "sessions",
        lazy: page(() => import("@/features/auth/SessionsPage"), "SessionsPage"),
      },
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
