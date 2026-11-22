import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { isNativeApp } from "@/platform";
import { api, type Schemas } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button, Dialog, DialogActions, TextField } from "@/shared/ui";

import styles from "./AccountPages.module.css";

type MyCalendar = Schemas["MyCalendar"];

const NONE: MyCalendar = { url: null, created_at: null, last_used_at: null };

function when(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    timeZone: "Asia/Tashkent",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** «Расписание в календаре»: a personal iCal link, reissue and revoke. */
export function CalendarSection({ activeRole: role }: { activeRole: "teacher" | "student" }) {
  const queryClient = useQueryClient();
  const key = ["me", "calendar", role];
  const feed = useQuery({ queryKey: key, queryFn: () => api<MyCalendar>("/me/calendar") });
  const [confirm, setConfirm] = useState(false);
  const [copied, setCopied] = useState(false);
  const issue = useMutation({
    mutationFn: () => api<MyCalendar>("/me/calendar", { method: "POST" }),
    onSuccess: (data) => {
      queryClient.setQueryData(key, data);
      setConfirm(false);
      setCopied(false);
    },
  });
  const revoke = useMutation({
    mutationFn: () => api<void>("/me/calendar", { method: "DELETE" }),
    onSuccess: () => queryClient.setQueryData(key, NONE),
  });

  const data = feed.data;
  const url = data?.url;
  const error = issue.error ?? revoke.error ?? feed.error;

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className={styles.section} aria-labelledby="calendar-title">
      <h2 id="calendar-title">{t("calendar.title")}</h2>
      <p className={styles.meta}>
        {t(role === "teacher" ? "calendar.hintTeacher" : "calendar.hint")}
      </p>
      {data && !url && (
        <div className={styles.actions}>
          <Button variant="primary" onClick={() => issue.mutate()} disabled={issue.isPending}>
            {t("calendar.create")}
          </Button>
        </div>
      )}
      {url && data && (
        <>
          <TextField
            label={t("calendar.link")}
            value={url}
            readOnly
            onFocus={(e) => e.currentTarget.select()}
            hint={
              data.created_at
                ? t("calendar.status", {
                    created: when(data.created_at),
                    used: data.last_used_at ? when(data.last_used_at) : t("calendar.neverUsed"),
                  })
                : undefined
            }
          />
          <div className={styles.actions}>
            <Button onClick={copy}>{copied ? t("calendar.copied") : t("calendar.copy")}</Button>
            {!isNativeApp && <a href={url.replace(/^https?:/, "webcal:")}>{t("calendar.open")}</a>}
            <Button onClick={() => setConfirm(true)}>{t("calendar.reissue")}</Button>
            <Button variant="danger" onClick={() => revoke.mutate()} disabled={revoke.isPending}>
              {t("calendar.revoke")}
            </Button>
          </div>
          <p className={styles.meta}>{t("calendar.how")}</p>
          <p className={styles.meta}>{t("calendar.secret")}</p>
        </>
      )}
      {error && (
        <p className={styles.error} role="alert">
          {errorMessage(error)}
        </p>
      )}
      <Dialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("calendar.reissueTitle")}
        description={t("calendar.reissueText")}
      >
        <DialogActions>
          <Button onClick={() => setConfirm(false)}>{t("common.cancel")}</Button>
          <Button variant="primary" onClick={() => issue.mutate()} disabled={issue.isPending}>
            {t("calendar.reissue")}
          </Button>
        </DialogActions>
      </Dialog>
    </section>
  );
}
