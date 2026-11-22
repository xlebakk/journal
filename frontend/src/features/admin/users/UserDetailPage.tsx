import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router";

import { useReauth } from "@/features/auth/reauthContext";
import { SessionsTable } from "@/features/auth/SessionsPage";
import { NotFoundPage } from "@/app/NotFoundPage";
import { isApiError } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button, Dialog, DialogActions, EmptyState, RuledSkeleton } from "@/shared/ui";

import { usersApi, useInvalidateUsers, useUser, useUserSessions, type UserDetail } from "./api";
import { TemporaryPasswordDialog } from "./TemporaryPasswordDialog";
import { UserForm } from "./UserForm";
import { statusLabel } from "./labels";
import { ChildrenSection, ParentsSection } from "./FamilySection";
import { StudentExtras } from "./TargetsEditor";
import styles from "./Users.module.css";

function Actions({ user }: { user: UserDetail }) {
  const withReauth = useReauth();
  const invalidate = useInvalidateUsers();
  const [password, setPassword] = useState<string | null>(null);
  const [confirmArchive, setConfirmArchive] = useState(false);

  const run = useMutation({
    mutationFn: (action: string) => withReauth(() => usersApi.action(user.id, action)),
    onSuccess: () => invalidate(),
  });
  const reset = useMutation({
    mutationFn: () => usersApi.resetPassword(user.id),
    onSuccess: async (data) => {
      setPassword(data.temporary_password);
      await invalidate();
    },
  });
  const error = run.error ?? reset.error;
  const busy = run.isPending || reset.isPending;

  return (
    <section className={styles.page} aria-labelledby="user-actions">
      <h2 id="user-actions">{t("userActions.title")}</h2>
      {user.login_locked_minutes > 0 && (
        <p className={styles.warning}>
          {t("userActions.lockedFor", { minutes: user.login_locked_minutes })}
        </p>
      )}
      <div className={styles.actions}>
        <Button onClick={() => reset.mutate()} disabled={busy || user.status === "archived"}>
          {t("userActions.resetPassword")}
        </Button>
        {user.login_locked_minutes > 0 && (
          <Button onClick={() => run.mutate("unlock-login")} disabled={busy}>
            {t("userActions.unlockLogin")}
          </Button>
        )}
        {user.totp_enabled && (
          <Button onClick={() => run.mutate("reset-2fa")} disabled={busy}>
            {t("userActions.reset2fa")}
          </Button>
        )}
        {user.status === "active" && (
          <Button variant="danger" onClick={() => run.mutate("block")} disabled={busy}>
            {t("userActions.block")}
          </Button>
        )}
        {user.status === "blocked" && (
          <Button onClick={() => run.mutate("unblock")} disabled={busy}>
            {t("userActions.unblock")}
          </Button>
        )}
        {user.status !== "archived" && (
          <Button variant="danger" onClick={() => setConfirmArchive(true)} disabled={busy}>
            {t("userActions.archive")}
          </Button>
        )}
      </div>
      {error && !(error instanceof Error && error.message === "reauth_cancelled") && (
        <p className={styles.error} role="alert">
          {errorMessage(error)}
        </p>
      )}

      <TemporaryPasswordDialog
        credentials={password ? { login: user.login, password } : null}
        onClose={() => setPassword(null)}
      />
      <Dialog
        open={confirmArchive}
        onOpenChange={setConfirmArchive}
        title={t("userActions.archive")}
        description={t("userActions.archiveConfirm")}
      >
        <DialogActions>
          <Button
            variant="primary"
            onClick={() => {
              setConfirmArchive(false);
              run.mutate("archive");
            }}
          >
            {t("userActions.archive")}
          </Button>
          <Button onClick={() => setConfirmArchive(false)}>{t("common.cancel")}</Button>
        </DialogActions>
      </Dialog>
    </section>
  );
}

function UserSessions({ userId }: { userId: string }) {
  const sessions = useUserSessions(userId);
  const end = useMutation({
    mutationFn: (sessionId: string) => usersApi.endSession(userId, sessionId),
    onSuccess: () => sessions.refetch(),
  });
  const endAll = useMutation({
    mutationFn: () => usersApi.endAllSessions(userId),
    onSuccess: () => sessions.refetch(),
  });
  return (
    <section className={styles.page} aria-labelledby="user-sessions">
      <h2 id="user-sessions">{t("userActions.sessionsTitle")}</h2>
      {sessions.isPending ? (
        <RuledSkeleton rows={2} />
      ) : sessions.data && sessions.data.length > 0 ? (
        <>
          <SessionsTable
            sessions={sessions.data.map((s) => ({ ...s, current: false }))}
            onEnd={(s) => end.mutate(s.id)}
            busy={end.isPending}
          />
          <div className={styles.actions}>
            <Button variant="danger" onClick={() => endAll.mutate()} disabled={endAll.isPending}>
              {t("userActions.endAll")}
            </Button>
          </div>
        </>
      ) : (
        <EmptyState text={t("sessions.empty")} />
      )}
    </section>
  );
}

export function UserDetailPage() {
  const { id = "" } = useParams();
  const user = useUser(id);
  const withReauth = useReauth();
  const invalidate = useInvalidateUsers();

  if (user.isPending) return <RuledSkeleton rows={6} />;
  if (isApiError(user.error, 404)) return <NotFoundPage />;
  if (user.error) return <p className={styles.error}>{errorMessage(user.error)}</p>;
  const data = user.data;

  return (
    <div className={styles.page}>
      <div className={styles.detailHeader}>
        <h1 className={styles.detailName}>{data.full_name}</h1>
        <span className={styles.status}>
          <span className="mono">{data.login}</span> · {statusLabel(data.status)}
        </span>
      </div>
      <UserForm
        user={data}
        submitLabel={t("userForm.save")}
        onSubmit={async (payload) => {
          // Changing roles is a dangerous action: the server may ask for the password again.
          await withReauth(() => usersApi.update(data.id, payload));
          await invalidate();
        }}
      />
      {data.roles.includes("student") && <StudentExtras userId={data.id} />}
      {data.roles.includes("student") && <ParentsSection student={data} />}
      {data.roles.includes("parent") && <ChildrenSection parentId={data.id} />}
      <Actions user={data} />
      <UserSessions userId={data.id} />
    </div>
  );
}
