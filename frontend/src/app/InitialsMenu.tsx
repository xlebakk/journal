import * as Menu from "@radix-ui/react-dropdown-menu";
import { ChevronDown } from "lucide-react";
import { useNavigate } from "react-router";

import { homePath, logout, useSwitchRole, type Me, type Role } from "@/features/auth/api";
import { queueSnapshot } from "@/features/journal/offlineQueue";
import { t, language, LANGUAGES, setLanguage, type Language } from "@/shared/i18n";
import { initialsOf } from "@/shared/ui";

import styles from "./InitialsMenu.module.css";

/** The stamp in the header corner and its keyboard-operable menu. */
export function InitialsMenu({ me }: { me: Me }) {
  const navigate = useNavigate();
  const switchRole = useSwitchRole();
  const otherRoles = me.roles.filter((role) => role !== me.active_role);

  const onSwitch = async (role: Role) => {
    const updated = await switchRole.mutateAsync(role);
    navigate(homePath(updated.active_role), { replace: true });
  };

  // Not modal: a modal menu locks scrolling with an injected <style>, which the CSP blocks.
  const studentLike = me.active_role === "student" || me.active_role === "parent";
  return (
    <Menu.Root modal={false}>
      <Menu.Trigger
        className={styles.profile}
        aria-label={t("stamp.menu", { name: `${me.first_name} ${me.last_name}` })}
      >
        <span className={styles.avatar} aria-hidden="true">
          {initialsOf(me.first_name, me.last_name)}
        </span>
        <span className={styles.profileText}>
          <span className={styles.profileName}>{me.full_name}</span>
          {me.active_role && (
            <span className={styles.profileRole}>
              {me.active_role === "admin" && me.position
                ? me.position
                : me.is_superadmin && me.active_role === "admin"
                  ? t("roles.superadmin")
                  : t(`roles.${me.active_role}`)}
            </span>
          )}
        </span>
        <ChevronDown size={16} strokeWidth={1.75} aria-hidden="true" className={styles.chevron} />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content className={styles.content} align="end" sideOffset={8}>
          <div className={styles.who}>
            <span className={styles.name}>{me.full_name}</span>
            {me.active_role && <span className={styles.role}>{t(`roles.${me.active_role}`)}</span>}
            {me.groups.length > 0 && (
              <span className={styles.role}>{me.groups.map((g) => g.name).join(", ")}</span>
            )}
          </div>
          <Menu.Separator className={styles.separator} />
          <Menu.Item className={styles.item} onSelect={() => navigate("/account/profile")}>
            {t("menu.profile")}
          </Menu.Item>
          {studentLike && (
            <Menu.Item className={styles.item} onSelect={() => navigate("/student/attendance")}>
              {t("nav.attendance")}
            </Menu.Item>
          )}
          {studentLike && (
            <Menu.Item className={styles.item} onSelect={() => navigate("/student/payments")}>
              {t("nav.payments")}
            </Menu.Item>
          )}
          <Menu.Item className={styles.item} onSelect={() => navigate("/account/password")}>
            {t("menu.password")}
          </Menu.Item>
          <Menu.Item className={styles.item} onSelect={() => navigate("/account/sessions")}>
            {t("menu.sessions")}
          </Menu.Item>
          <Menu.Separator className={styles.separator} />
          <Menu.Label className={styles.label}>{t("language.label")}</Menu.Label>
          <Menu.RadioGroup
            value={language()}
            onValueChange={(value) => setLanguage(value as Language)}
          >
            {LANGUAGES.map((option) => (
              <Menu.RadioItem key={option} value={option} className={styles.item} lang={option}>
                <Menu.ItemIndicator className={styles.indicator}>•</Menu.ItemIndicator>
                {t(`language.${option}`)}
              </Menu.RadioItem>
            ))}
          </Menu.RadioGroup>
          {otherRoles.length > 0 && <Menu.Separator className={styles.separator} />}
          {otherRoles.map((role) => (
            <Menu.Item key={role} className={styles.item} onSelect={() => void onSwitch(role)}>
              {t("menu.switchRole", { role: t(`roles.${role}`) })}
            </Menu.Item>
          ))}
          <Menu.Separator className={styles.separator} />
          <Menu.Item
            className={styles.item}
            onSelect={() => {
              // Unsent offline changes live only in this tab (stage 13).
              if (
                queueSnapshot().pending.length > 0 &&
                !window.confirm(t("offline.logoutConfirm"))
              ) {
                return;
              }
              void logout();
            }}
          >
            {t("menu.logout")}
          </Menu.Item>
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}
