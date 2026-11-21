import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { requestSummary } from "@/features/teacher/requestSummary";
import { useInvalidateSchedule, type ScheduleRequest } from "@/features/schedule/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, type Schemas } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDayLong, hhmm } from "@/shared/lib/week";
import { Button, EmptyState, RuledSkeleton, ScheduleIssues, Table, TextField } from "@/shared/ui";

import { issuesOf } from "./api";

type Page = Schemas["PaginatedScheduleRequestList"];

/** Teachers' requests to cancel or move lessons; approving applies the change (SPEC §9). */
export function RequestsPage() {
  const requests = useQuery({
    queryKey: ["admin", "schedule-requests", "pending"],
    queryFn: () => api<Page>("/admin/schedule-requests", { query: { status: "pending" } }),
  });
  const invalidate = useInvalidateSchedule();
  const [comments, setComments] = useState<Record<string, string>>({});
  const resolve = useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: "approve" | "reject" }) =>
      api<ScheduleRequest>(`/admin/schedule-requests/${id}/${verb}`, {
        method: "POST",
        body: { comment: comments[id] ?? "" },
      }),
    onSuccess: () => invalidate(),
  });
  const items = requests.data?.results ?? [];
  const { conflicts } = issuesOf(resolve.error);

  return (
    <section className={styles.page}>
      <h1>{t("schedule.requestsTitle")}</h1>
      <ScheduleIssues conflicts={conflicts} />
      {resolve.error && !conflicts.length && (
        <p className={styles.error} role="alert">
          {errorMessage(resolve.error)}
        </p>
      )}
      {requests.isPending ? (
        <RuledSkeleton rows={3} />
      ) : items.length === 0 ? (
        <EmptyState text={t("schedule.requestsEmpty")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("schedule.lessonTitle")}</th>
              <th scope="col">{t("schedule.teacher")}</th>
              <th scope="col">{t("schedule.requestReason")}</th>
              <th scope="col">{t("schedule.comment")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("schedule.approve")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id}>
                <td>
                  {r.lesson_info.group_name} · {r.lesson_info.subject_name},{" "}
                  {formatDayLong(r.lesson_info.date)}{" "}
                  <span className="mono">{hhmm(r.lesson_info.start_time)}</span> —{" "}
                  {requestSummary(r)}
                </td>
                <td>{r.author_name}</td>
                <td>{r.reason}</td>
                <td>
                  <TextField
                    label={t("schedule.comment")}
                    value={comments[r.id] ?? ""}
                    onChange={(e) => setComments((c) => ({ ...c, [r.id]: e.target.value }))}
                  />
                </td>
                <td>
                  <span className={styles.row}>
                    <Button
                      variant="primary"
                      disabled={resolve.isPending}
                      onClick={() => resolve.mutate({ id: r.id, verb: "approve" })}
                    >
                      {t("schedule.approve")}
                    </Button>
                    <Button
                      variant="danger"
                      disabled={resolve.isPending}
                      onClick={() => resolve.mutate({ id: r.id, verb: "reject" })}
                    >
                      {t("schedule.reject")}
                    </Button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </section>
  );
}
