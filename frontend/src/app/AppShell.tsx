import { NavLink, Outlet } from "react-router";

import type { Me, Role } from "@/features/auth/api";
import { useBranding } from "@/features/auth/api";
import { t, type MessageKey } from "@/shared/i18n";

import styles from "./AppShell.module.css";
import { InitialsMenu } from "./InitialsMenu";

type NavItem = { to: string; label: MessageKey; end?: boolean };

// Only sections that exist today; the rest appear with their stages.
const NAV: Record<Role, NavItem[]> = {
  admin: [
    { to: "/admin", label: "nav.overview", end: true },
    { to: "/admin/users", label: "nav.users" },
    { to: "/admin/groups", label: "nav.groups" },
    { to: "/admin/schedule", label: "nav.schedule" },
    { to: "/admin/requests", label: "nav.requests" },
    { to: "/admin/catalogs", label: "nav.catalogs" },
  ],
  teacher: [
    { to: "/teacher", label: "nav.today", end: true },
    { to: "/teacher/schedule", label: "nav.schedule" },
  ],
  student: [
    { to: "/student", label: "nav.home", end: true },
    { to: "/student/schedule", label: "nav.schedule" },
  ],
  parent: [],
};

function Links({ items, className }: { items: NavItem[]; className: string | undefined }) {
  return (
    <>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            [className, isActive && styles.active].filter(Boolean).join(" ")
          }
        >
          {t(item.label)}
        </NavLink>
      ))}
    </>
  );
}

/** Header: center name, text tabs, stamp. Administrators get a narrow left column (SPEC §8). */
export function AppShell({ me }: { me: Me }) {
  const branding = useBranding();
  const role = me.active_role ?? "student";
  const items = NAV[role];
  const isAdmin = role === "admin";
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <span className={styles.brand}>{branding.data?.center_name || t("app.centerName")}</span>
        {!isAdmin && (
          <nav className={styles.tabs} aria-label={t("nav.sections")}>
            <Links items={items} className={styles.tab} />
          </nav>
        )}
        <span className={styles.spacer} />
        <InitialsMenu me={me} />
      </header>
      <div className={isAdmin ? styles.withSidebar : styles.body}>
        {isAdmin && (
          <nav className={styles.sidebar} aria-label={t("nav.sections")}>
            <Links items={items} className={styles.sideLink} />
          </nav>
        )}
        <main className={styles.main}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
