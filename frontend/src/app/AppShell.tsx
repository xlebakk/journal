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
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  ShieldCheck,
  Sun,
  Upload,
  Users,
  UsersRound,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";

import type { Me, Role } from "@/features/auth/api";
import { t, type MessageKey } from "@/shared/i18n";

import { EmptyState, Logo } from "@/shared/ui";
import { OfflineBar } from "@/features/journal/OfflineBar";
import { ChildSwitcher } from "@/features/parent/ChildSwitcher";
import { useHasChildren } from "@/features/parent/children";
import styles from "./AppShell.module.css";
import { InitialsMenu } from "./InitialsMenu";
import { ThemeToggle } from "./ThemeToggle";
import { preloadScreens } from "./preload";

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
            // A folded sidebar shows only icons: the name comes as a tooltip.
            title={icons ? t(item.label) : undefined}
          >
            {Icon && <Icon size={18} strokeWidth={1.75} aria-hidden="true" />}
            {icons ? <span className={styles.sideLabel}>{t(item.label)}</span> : t(item.label)}
          </NavLink>
        );
      })}
    </>
  );
}

const FOLD_KEY = "journal.sidebarFolded";

/** The administrator's sidebar folded to icons (stage 19); remembered on this device. */
function useFoldedSidebar(): [boolean, (folded: boolean) => void] {
  const [folded, setFolded] = useState(() => {
    try {
      return localStorage.getItem(FOLD_KEY) === "1";
    } catch {
      return false;
    }
  });
  const change = (next: boolean) => {
    setFolded(next);
    try {
      localStorage.setItem(FOLD_KEY, next ? "1" : "0");
    } catch {
      // Private mode: the choice lasts for this page only.
    }
  };
  return [folded, change];
}

/** Header: the product, the sections in the middle, the person. Administrators get a left column. */
export function AppShell({ me }: { me: Me }) {
  const location = useLocation();
  const [folded, setFolded] = useFoldedSidebar();
  // Once signed in, the other screens' code comes in idle time.
  useEffect(preloadScreens, []);
  const role = me.active_role ?? "student";
  // An administrator sees only the sections the super administrator granted (stage 16).
  const items = NAV[role].filter(
    (item) =>
      !item.section || me.is_superadmin || me.admin_sections.includes(item.section as never),
  );
  const isAdmin = role === "admin";
  const isParent = role === "parent";
  const studentLike = role === "student" || isParent;
  // Phones: a bottom bar of five items with icons instead of header tabs.
  const bottomBar = studentLike || role === "teacher";
  const hasChildren = useHasChildren(isParent);
  return (
    <div className={bottomBar ? `${styles.shell} ${styles.withBottomNav}` : styles.shell}>
      <header className={styles.header}>
        <Logo className={styles.brand} />
        {isAdmin ? (
          <span />
        ) : (
          <nav
            className={bottomBar ? `${styles.tabs} ${styles.studentTabs}` : styles.tabs}
            aria-label={t("nav.sections")}
          >
            <Links items={items} className={styles.tab} />
          </nav>
        )}
        <div className={styles.aside}>
          <ThemeToggle />
          {isParent && <ChildSwitcher />}
          <InitialsMenu me={me} />
        </div>
      </header>
      <div
        className={
          isAdmin
            ? [styles.withSidebar, folded && styles.folded].filter(Boolean).join(" ")
            : styles.body
        }
      >
        {isAdmin && (
          <nav className={styles.sidebar} aria-label={t("nav.sections")}>
            <button
              type="button"
              className={styles.fold}
              aria-expanded={!folded}
              aria-label={folded ? t("nav.unfold") : t("nav.fold")}
              title={folded ? t("nav.unfold") : t("nav.fold")}
              onClick={() => setFolded(!folded)}
            >
              {folded ? (
                <PanelLeftOpen size={18} strokeWidth={1.75} aria-hidden="true" />
              ) : (
                <PanelLeftClose size={18} strokeWidth={1.75} aria-hidden="true" />
              )}
            </button>
            <Links items={items} className={styles.sideLink} icons />
          </nav>
        )}
        <main className={styles.main}>
          {(role === "teacher" || isAdmin) && <OfflineBar />}
          {isParent && hasChildren === false ? (
            <EmptyState text={t("parent.noChildren")} />
          ) : (
            <div key={location.pathname} className={styles.pageIn}>
              <Outlet />
            </div>
          )}
        </main>
      </div>
      {bottomBar && (
        // Phones: a bottom bar of five items with thin icons and labels.
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
