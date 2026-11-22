import { useNavigate } from "react-router";

import { t } from "@/shared/i18n";

import { usersApi, useInvalidateUsers } from "./api";
import { UserForm } from "./UserForm";
import styles from "./Users.module.css";

/** A new account: the administrator types the password (stage 16); then the user's card. */
export function UserCreatePage() {
  const navigate = useNavigate();
  const invalidate = useInvalidateUsers();
  return (
    <section className={styles.page}>
      <h1>{t("userForm.newTitle")}</h1>
      <UserForm
        submitLabel={t("userForm.create")}
        onSubmit={async (payload) => {
          const user = await usersApi.create(payload);
          await invalidate();
          navigate(`/admin/users/${user.id}`, { replace: true });
        }}
      />
    </section>
  );
}
