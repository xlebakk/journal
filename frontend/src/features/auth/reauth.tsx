import { useCallback, useRef, useState, type ReactNode } from "react";

import { ApiError } from "@/shared/api/client";
import { fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button, Dialog, DialogActions, PasswordField } from "@/shared/ui";

import { reauthenticate } from "./api";
import { ReauthContext, type WithReauth } from "./reauthContext";

/**
 * Dangerous actions answer 403 reauth_required when the password was last entered more than
 * five minutes ago. This asks for it once and repeats the action.
 */
export function ReauthProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const waiter = useRef<{ resolve: () => void; reject: (e: unknown) => void } | null>(null);

  const askPassword = useCallback(
    () =>
      new Promise<void>((resolve, reject) => {
        waiter.current = { resolve, reject };
        setPassword("");
        setError(null);
        setOpen(true);
      }),
    [],
  );

  const withReauth = useCallback<WithReauth>(
    async (action) => {
      try {
        return await action();
      } catch (e) {
        if (!(e instanceof ApiError && e.code === "reauth_required")) throw e;
        await askPassword();
        return action();
      }
    },
    [askPassword],
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setPending(true);
    try {
      await reauthenticate(password);
      setOpen(false);
      waiter.current?.resolve();
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  };

  const cancel = (next: boolean) => {
    if (next) return;
    setOpen(false);
    waiter.current?.reject(new Error("reauth_cancelled"));
  };

  return (
    <ReauthContext.Provider value={withReauth}>
      {children}
      <Dialog
        open={open}
        onOpenChange={cancel}
        title={t("reauth.title")}
        description={t("reauth.note")}
      >
        <form onSubmit={submit} noValidate>
          <PasswordField
            label={t("login.password")}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={
              fieldError(error, "password") ??
              (error instanceof ApiError && error.code
                ? t("errors.too_many_attempts", {
                    minutes: error.field<number>("retry_after_minutes") ?? "",
                  })
                : undefined)
            }
          />
          <DialogActions>
            <Button type="submit" variant="primary" disabled={pending || !password}>
              {t("reauth.submit")}
            </Button>
            <Button onClick={() => cancel(false)}>{t("common.cancel")}</Button>
          </DialogActions>
        </form>
      </Dialog>
    </ReauthContext.Provider>
  );
}
