import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, type Schemas } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDate } from "@/shared/lib/week";
import { EmptyState, RuledSkeleton, TextField } from "@/shared/ui";

import styles from "./Journal.module.css";

type Reviews = Schemas["Reviews"];
type Row = Schemas["ReviewRow"];

const UUID = /^[0-9a-f-]{36}$/i;

const reviewsKey = (course: string, termId: string | undefined) =>
  ["journal", "reviews", course, termId ?? "current"] as const;

/** One student's review: saved when the field loses focus, if it changed. */
function ReviewRow({
  course,
  queryKey,
  reviews,
  row,
  reason,
}: {
  course: string;
  queryKey: ReturnType<typeof reviewsKey>;
  reviews: Reviews;
  row: Row;
  reason: string;
}) {
  const queryClient = useQueryClient();
  const [text, setText] = useState(row.text);
  const save = useMutation({
    mutationFn: () =>
      api<Row>(`/journal/courses/${course}/reviews/${row.student}`, {
        method: "PUT",
        body: { term: reviews.term.id, text, version: row.version, reason },
      }),
    onSuccess: (next) => {
      setText(next.text);
      queryClient.setQueryData<Reviews>(queryKey, (old) =>
        old ? { ...old, rows: old.rows.map((r) => (r.student === next.student ? next : r)) } : old,
      );
    },
  });
  const editable = reviews.editable && (!reviews.needs_reason || reason.trim() !== "");
  const id = `review-${row.student}`;
  return (
    <li className={styles.reviewRow}>
      <label htmlFor={id} className={styles.reviewName}>
        {row.full_name}
      </label>
      <textarea
        id={id}
        className={styles.textarea}
        rows={3}
        maxLength={reviews.max_length}
        value={text}
        disabled={!editable || save.isPending}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => text.trim() !== row.text && save.mutate()}
      />
      <p className={styles.note}>
        {text.length} / {reviews.max_length}
        {row.author_name && row.updated_at && (
          <>
            {" "}
            · {row.author_name}, {formatDate(row.updated_at.slice(0, 10))}
          </>
        )}
        {save.isSuccess && <> · {t("common.saved")}</>}
      </p>
      {save.error && (
        <p className={styles.error} role="alert">
          {fieldError(save.error, "text") ?? errorMessage(save.error)}
        </p>
      )}
    </li>
  );
}

/** «Отзывы» (SPEC §16.5): two or three sentences per student, once per term. */
export function ReviewsTab({ course, term }: { course: string; term: string | undefined }) {
  const termId = term && UUID.test(term) ? term : undefined;
  const [reason, setReason] = useState("");
  const queryKey = reviewsKey(course, termId);
  const reviews = useQuery({
    queryKey,
    queryFn: () => api<Reviews>(`/journal/courses/${course}/reviews`, { query: { term: termId } }),
  });
  if (reviews.isPending) return <RuledSkeleton rows={6} />;
  if (reviews.error || !reviews.data) {
    return <p className={styles.error}>{errorMessage(reviews.error)}</p>;
  }
  const data = reviews.data;
  const closes = formatDate(data.closes_on);
  return (
    <section className={styles.reviews} aria-labelledby="reviews-title">
      <h2 id="reviews-title">{t("reviews.title", { term: data.term.name })}</h2>
      <p className={styles.note}>{t("reviews.hint")}</p>
      {data.locked === "not_course_teacher" && (
        <p className={styles.note}>{t("reviews.readOnly")}</p>
      )}
      {data.locked === "future" && <p className={styles.note}>{t("reviews.future")}</p>}
      {data.locked === "window" && (
        <p className={styles.note}>{t("reviews.closed", { date: closes })}</p>
      )}
      {data.needs_reason && (
        <>
          <p className={styles.note}>{t("reviews.needsReason", { date: closes })}</p>
          <TextField
            label={t("journal.reasonField")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </>
      )}
      {data.rows.length === 0 ? (
        <EmptyState text={t("reviews.noStudents")} />
      ) : (
        <ul className={styles.reviewList}>
          {data.rows.map((row) => (
            <ReviewRow
              key={`${data.term.id}-${row.student}`}
              course={course}
              queryKey={queryKey}
              reviews={data}
              row={row}
              reason={reason}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
