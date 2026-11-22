import { useId, useState } from "react";
import { Link, useParams } from "react-router";

import { NotFoundPage } from "@/app/NotFoundPage";
import { useMe } from "@/features/auth/api";
import { isApiError } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDate, formatDayLong, hhmm } from "@/shared/lib/week";
import { Button, EmptyState, RuledSkeleton, SelectField, TextField } from "@/shared/ui";

import { journalApi, useLessonPage, type LessonPageData } from "./api";
import styles from "./Journal.module.css";
import { journalBase } from "./paths";
import { SaveStatus } from "./SaveStatus";
import { StudentEditor } from "./StudentEditor";
import { allPresentAction, lessonAction } from "./actions";
import { useQueue } from "./offlineQueue";
import { useOnline } from "./useOnline";
import { useSave, type Action } from "./useSave";

type Draft = { topic: string; homework: string; comment: string };

function Header({ data }: { data: LessonPageData }) {
  const { lesson, course } = data;
  return (
    <div className={styles.lessonHead}>
      <h1>
        {course.subject_name} · {course.group_name}
      </h1>
      <p className={`mono ${styles.lessonMeta}`}>
        {formatDayLong(lesson.date)} · {hhmm(lesson.start_time)}–{hhmm(data.end_time)}
        {data.room_name && <> · {t("schedule.room", { room: data.room_name })}</>} ·{" "}
        {data.teacher_name}
      </p>
      <p className={styles.lessonMeta}>
        {lesson.status === "conducted" && <>{t("journal.conducted")} · </>}
        {lesson.locked === "window" || lesson.needs_reason
          ? t("journal.windowClosed", { date: formatDate(data.window_closes_on) })
          : lesson.locked === "future"
            ? t("journal.futureHint")
            : t("journal.windowOpen", { date: formatDate(data.window_closes_on) })}
      </p>
    </div>
  );
}

type FieldsProps = {
  data: LessonPageData;
  reason: string;
  blocked: boolean;
  busy: boolean;
  perform: (action: Action) => Promise<boolean>;
  onDraft: (draft: Draft) => void;
};

/** Keyed by the lesson version: after every saved change it starts from the server values. */
function LessonFields({ data, reason, blocked, busy, perform, onDraft }: FieldsProps) {
  const { lesson } = data;
  const [values, setValues] = useState<Draft>({
    topic: lesson.topic,
    homework: lesson.homework,
    comment: data.comment,
  });
  const suggestions = useId();
  const save = (changes: Record<string, unknown>, label: string) =>
    void perform(lessonAction(lesson, changes, reason, label));
  const change = (name: keyof Draft, value: string) => {
    const next = { ...values, [name]: value };
    setValues(next);
    onDraft(next);
  };

  return (
    <div className={styles.fields}>
      <SelectField
        label={t("journal.lessonType")}
        value={lesson.lesson_type ?? ""}
        disabled={blocked || busy}
        onChange={(e) => save({ lesson_type: e.target.value || null }, t("journal.lessonType"))}
        options={[
          { value: "", label: "—" },
          ...data.lesson_types.map((x) => ({ value: x.id, label: x.name })),
        ]}
      />
      <TextField
        label={t("journal.topic")}
        value={values.topic}
        list={suggestions}
        disabled={blocked}
        onChange={(e) => change("topic", e.target.value)}
        onBlur={() =>
          values.topic !== lesson.topic && save({ topic: values.topic }, t("journal.topic"))
        }
      />
      <datalist id={suggestions}>
        {data.topic_suggestions.map((x) => (
          <option key={x} value={x} />
        ))}
      </datalist>
      <label className={styles.textareaField}>
        <span className={styles.label}>{t("journal.homework")}</span>
        <textarea
          className={styles.textarea}
          value={values.homework}
          disabled={blocked}
          rows={2}
          onChange={(e) => change("homework", e.target.value)}
          onBlur={() =>
            values.homework !== lesson.homework &&
            save({ homework: values.homework }, t("journal.homework"))
          }
        />
      </label>
      <details className={styles.more} open={Boolean(values.comment)}>
        <summary>{t("journal.comment")}</summary>
        <label className={styles.textareaField}>
          <span className="visually-hidden">{t("journal.comment")}</span>
          <textarea
            className={styles.textarea}
            value={values.comment}
            disabled={blocked}
            rows={2}
            onChange={(e) => change("comment", e.target.value)}
            onBlur={() =>
              values.comment !== data.comment &&
              save({ comment: values.comment }, t("journal.comment"))
            }
          />
        </label>
      </details>
    </div>
  );
}

/** The lesson page — the teacher's main screen (SPEC §7.2). */
export function LessonPage() {
  const { id = "" } = useParams();
  const me = useMe();
  const page = useLessonPage(id);
  const { state, perform, retry, undo, busy } = useSave();
  const queue = useQueue();
  const online = useOnline();
  const [reason, setReason] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);

  const data = page.data;
  if (page.isPending) return <RuledSkeleton rows={8} />;
  if (isApiError(page.error, 404)) return <NotFoundPage />;
  if (page.error || !data) return <p className={styles.error}>{errorMessage(page.error)}</p>;

  const { lesson, rules } = data;
  const isAdmin = me.data?.active_role === "admin";
  const ref = { id: lesson.id, editable: lesson.editable, needs_reason: lesson.needs_reason };
  const blocked = !lesson.editable || (lesson.needs_reason && !reason.trim());

  const conduct = () =>
    void perform({
      run: async () => {
        // Unmarked students are «был» by default: save that first (SPEC §7.2).
        await journalApi.allPresent(lesson.id, { reason });
        const fields = draft ?? {
          topic: lesson.topic,
          homework: lesson.homework,
          comment: data.comment,
        };
        const fresh = await journalApi.updateLesson(lesson.id, {
          version: lesson.version,
          reason,
          ...fields,
        });
        return journalApi.conduct(lesson.id, { version: fresh.lesson.version, reason });
      },
    });

  return (
    <section className={styles.page}>
      <Link
        to={`${journalBase(me.data?.active_role)}?course=${data.course.id}`}
        className={styles.backLink}
      >
        ← {t("journal.back")}
      </Link>
      <Header data={data} />

      {lesson.needs_reason && (
        <div className={styles.reasonBox}>
          <p className={styles.note}>
            {t("journal.reasonNote", { date: formatDate(data.window_closes_on) })}
          </p>
          <TextField
            label={t("journal.reasonField")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
      )}

      <LessonFields
        key={`${lesson.id}:${lesson.version}`}
        data={data}
        reason={reason}
        blocked={blocked}
        busy={busy}
        perform={perform}
        onDraft={setDraft}
      />

      <h2>{t("journal.students")}</h2>
      {data.students.length === 0 ? (
        <EmptyState text={t("journal.noStudents")} />
      ) : (
        <div className={styles.students}>
          {data.students.map((student) => (
            <StudentEditor
              key={student.id}
              lesson={ref}
              rules={rules}
              workTypes={data.work_types}
              student={student}
              attendance={data.attendance.find((a) => a.student === student.id)}
              grades={data.grades.filter((g) => g.student === student.id)}
              reason={reason}
              isAdmin={isAdmin}
              busy={busy}
              perform={perform}
            />
          ))}
        </div>
      )}

      <div className={styles.actions}>
        <Button
          disabled={blocked || busy}
          onClick={() => void perform(allPresentAction(lesson.id, reason))}
        >
          {t("journal.allPresent")}
        </Button>
        {lesson.status !== "conducted" && (
          <Button
            variant="primary"
            disabled={blocked || busy || !online || queue.pending.length > 0}
            title={!online || queue.pending.length > 0 ? t("offline.needsNetwork") : undefined}
            onClick={conduct}
          >
            {t("journal.conduct")}
          </Button>
        )}
        <SaveStatus state={state} retry={retry} undo={undo} />
      </div>
    </section>
  );
}
