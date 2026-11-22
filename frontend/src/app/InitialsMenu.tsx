import * as Menu from "@radix-ui/react-dropdown-menu";
import { useNavigate } from "react-router";

import { homePath, logout, useSwitchRole, type Me, type Role } from "@/features/auth/api";
import { t } from "@/shared/i18n";
import { useTheme, type ThemePreference } from "@/shared/lib/theme";
import { InitialsStamp } from "@/shared/ui";

import styles from "./InitialsMenu.module.css";

const THEMES: ThemePreference[] = ["light", "dark", "system"];

/** The stamp in the header corner and its keyboard-operable menu (SPEC §4). */
export function InitialsMenu({ me }: { me: Me }) {
  const navigate = useNavigate();
  const [theme, setTheme] = useTheme();
  const switchRole = useSwitchRole();
  const otherRoles = me.roles.filter((role) => role !== me.active_role);

  const onSwitch = async (role: Role) => {
    const updated = await switchRole.mutateAsync(role);
    navigate(homePath(updated.active_role), { replace: true });
  };

  // Not modal: a modal menu locks scrolling with an injected <style>, which the CSP blocks.
  return (
    <Menu.Root modal={false}>
      <Menu.Trigger asChild>
        <InitialsStamp userId={me.id} firstName={me.first_name} lastName={me.last_name} />
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
          {me.active_role === "student" && (
            <Menu.Item className={styles.item} onSelect={() => navigate("/student/attendance")}>
              {t("nav.attendance")}
            </Menu.Item>
          )}
          {me.active_role === "student" && (
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
          <Menu.Label className={styles.label}>{t("theme.label")}</Menu.Label>
          <Menu.RadioGroup
            value={theme}
            onValueChange={(value) => setTheme(value as ThemePreference)}
          >
            {THEMES.map((option) => (
              <Menu.RadioItem key={option} value={option} className={styles.item}>
                <Menu.ItemIndicator className={styles.indicator}>•</Menu.ItemIndicator>
                {t(`theme.${option}`)}
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
          <Menu.Item className={styles.item} onSelect={() => void logout()}>
            {t("menu.logout")}
          </Menu.Item>
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}
