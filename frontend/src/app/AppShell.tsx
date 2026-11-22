import {
  BookMarked,
  BookOpen,
  CalendarDays,
  ChartColumn,
  ClipboardList,
  FileCheck,
  House,
  Inbox,
  LayoutDashboard,
  Megaphone,
  NotebookPen,
  Settings,
  ShieldCheck,
  Sun,
  Upload,
  Users,
  UsersRound,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { NavLink, Outlet } from "react-router";

import type { Me, Role } from "@/features/auth/api";
import { useBranding } from "@/features/auth/api";
import { t, type MessageKey } from "@/shared/i18n";

import { EmptyState } from "@/shared/ui";
import { OfflineBar } from "@/features/journal/OfflineBar";
import { ChildSwitcher } from "@/features/parent/ChildSwitcher";
import { useHasChildren } from "@/features/parent/children";
import styles from "./AppShell.module.css";
import { InitialsMenu } from "./InitialsMenu";

type NavItem = {
  to: string;
  label: MessageKey;
  end?: boolean;
  icon?: LucideIcon;
  /** The administration section it belongs to (stage 16); none — every administrator. */
  section?: string;
};

const STUDENT_NAV: NavItem[] = [
  { to: "/student", label: "nav.home", end: true, icon: House },
  { to: "/student/diary", label: "nav.diary", icon: BookOpen },
  { to: "/student/grades", label: "nav.grades", icon: ClipboardList },
  { to: "/student/tests", label: "nav.tests", icon: FileCheck },
  { to: "/student/schedule", label: "nav.schedule", icon: CalendarDays },
];

const NAV: Record<Role, NavItem[]> = {
  admin: [
    { to: "/admin", label: "nav.overview", end: true, icon: LayoutDashboard },
    { to: "/admin/users", label: "nav.users", icon: Users, section: "users" },
    { to: "/admin/import", label: "nav.import", icon: Upload, section: "users" },
    { to: "/admin/groups", label: "nav.groups", icon: UsersRound, section: "structure" },
    { to: "/admin/catalogs", label: "nav.catalogs", icon: BookMarked, section: "structure" },
    { to: "/admin/schedule", label: "nav.schedule", icon: CalendarDays, section: "schedule" },
    { to: "/admin/requests", label: "nav.requests", icon: Inbox, section: "schedule" },
    { to: "/admin/journal", label: "nav.journal", icon: NotebookPen, section: "journal" },
    { to: "/admin/exams", label: "nav.exams", icon: FileCheck, section: "exams" },
    { to: "/admin/reports", label: "nav.reports", icon: ChartColumn, section: "reports" },
    { to: "/admin/payments", label: "nav.payments", icon: Wallet, section: "payments" },
    {
      to: "/admin/announcements",
      label: "nav.announcements",
      icon: Megaphone,
      section: "announcements",
    },
    { to: "/admin/audit", label: "nav.audit", icon: ShieldCheck, section: "audit" },
    { to: "/admin/settings", label: "nav.settings", icon: Settings, section: "settings" },
  ],
  teacher: [
    { to: "/teacher", label: "nav.today", end: true, icon: Sun },
    { to: "/teacher/journal", label: "nav.journal", icon: NotebookPen },
    { to: "/teacher/schedule", label: "nav.schedule", icon: CalendarDays },
    { to: "/teacher/exams", label: "nav.exams", icon: FileCheck },
    { to: "/teacher/reports", label: "nav.reports", icon: ChartColumn },
  ],
  student: STUDENT_NAV,
  // A parent reads the child's student pages (stage 14).
  parent: STUDENT_NAV,
};

function Links({
  items,
  className,
  icons = false,
}: {
  items: NavItem[];
  className: string | undefined;
  icons?: boolean;
}) {
  return (
    <>
      {items.map((item) => {
        const Icon = icons ? item.icon : undefined;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              [className, isActive && styles.active].filter(Boolean).join(" ")
            }
          >
            {Icon && <Icon size={18} strokeWidth={1.75} aria-hidden="true" />}
            {t(item.label)}
          </NavLink>
        );
      })}
    </>
  );
}

/** Header: center name, text tabs, stamp. Administrators get a narrow left column (SPEC §8). */
export function AppShell({ me }: { me: Me }) {
  const branding = useBranding();
  const role = me.active_role ?? "student";
  // An administrator sees only the sections the super administrator granted (stage 16).
  const items = NAV[role].filter(
    (item) =>
      !item.section || me.is_superadmin || me.admin_sections.includes(item.section as never),
  );
  const isAdmin = role === "admin";
  const isParent = role === "parent";
  const studentLike = role === "student" || isParent;
  // Phones: a bottom bar of five items with icons instead of header tabs (SPEC §6, §12).
  const bottomBar = studentLike || role === "teacher";
  const hasChildren = useHasChildren(isParent);
  return (
    <div className={bottomBar ? `${styles.shell} ${styles.withBottomNav}` : styles.shell}>
      <header className={styles.header}>
        <span className={styles.brand}>{branding.data?.center_name || t("app.centerName")}</span>
        {!isAdmin && (
          <nav
            className={bottomBar ? `${styles.tabs} ${styles.studentTabs}` : styles.tabs}
            aria-label={t("nav.sections")}
          >
            <Links items={items} className={styles.tab} />
          </nav>
        )}
        <span className={styles.spacer} />
        <div className={styles.aside}>
          {isParent && <ChildSwitcher />}
          <InitialsMenu me={me} />
        </div>
      </header>
      <div className={isAdmin ? styles.withSidebar : styles.body}>
        {isAdmin && (
          <nav className={styles.sidebar} aria-label={t("nav.sections")}>
            <Links items={items} className={styles.sideLink} icons />
          </nav>
        )}
        <main className={styles.main}>
          {(role === "teacher" || isAdmin) && <OfflineBar />}
          {isParent && hasChildren === false ? (
            <EmptyState text={t("parent.noChildren")} />
          ) : (
            <Outlet />
          )}
        </main>
      </div>
      {bottomBar && (
        // Phones: a bottom bar of five items with thin icons and labels (SPEC §6, §12).
        <nav className={styles.bottomNav} aria-label={t("nav.sections")}>
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  [styles.bottomLink, isActive && styles.active].filter(Boolean).join(" ")
                }
              >
                {Icon && <Icon size={20} strokeWidth={1.5} aria-hidden="true" />}
                <span>{t(item.label)}</span>
              </NavLink>
            );
          })}
        </nav>
      )}
    </div>
  );
}
