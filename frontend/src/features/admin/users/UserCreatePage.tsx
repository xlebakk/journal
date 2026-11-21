import { useState } from "react";
import { useNavigate } from "react-router";

import { t } from "@/shared/i18n";

import { usersApi, useInvalidateUsers, type TemporaryPassword } from "./api";
import { TemporaryPasswordDialog } from "./TemporaryPasswordDialog";
import { UserForm } from "./UserForm";
import styles from "./Users.module.css";

export function UserCreatePage() {
  const navigate = useNavigate();
  const invalidate = useInvalidateUsers();
  const [created, setCreated] = useState<TemporaryPassword | null>(null);

  return (
    <section className={styles.page}>
      <h1>{t("userForm.newTitle")}</h1>
      <UserForm
        submitLabel={t("userForm.create")}
        onSubmit={async (payload) => {
          const result = await usersApi.create(payload);
          await invalidate();
          setCreated(result);
        }}
      />
      <TemporaryPasswordDialog
        credentials={
          created ? { login: created.user.login, password: created.temporary_password } : null
        }
        onClose={() => created && navigate(`/admin/users/${created.user.id}`, { replace: true })}
      />
    </section>
  );
}
