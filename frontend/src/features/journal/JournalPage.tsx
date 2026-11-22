import { memo, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { useMe } from "@/features/auth/api";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { addDays, formatDate, isoWeekday } from "@/shared/lib/week";
import {
  Button,
  Dialog,
  DialogActions,
  EmptyState,
  RuledSkeleton,
  SelectField,
  TextField,
} from "@/shared/ui";

import {
  isLow,
  journalApi,
  SCALE_RANGE,
  useGrid,
  useJournalCourses,
  useTerms,
  type Attendance,
  type Grade,
  type Grid,
  type GridLesson,
  type RowStudent,
} from "./api";
import styles from "./Journal.module.css";
import { journalBase } from "./paths";
import { addGradeAction, deleteGradeAction, mark, statusFromKey } from "./actions";
import { StudentEditor } from "./StudentEditor";
import { SaveStatus } from "./SaveStatus";
import { useSave } from "./useSave";
import { ReviewsTab } from "./ReviewsTab";

type Cell = { attendance?: Attendance; grades: Grade[] };
type Maps = Map<string, Cell>;

const key = (lesson: string, student: string) => `${lesson}:${student}`;

function memberOn(student: RowStudent, day: string): boolean {
  return student.periods.some((p) => p.start <= day && (!p.end || day <= p.end));
}

function buildMaps(grid: Grid): Maps {
  const maps: Maps = new Map();
  const cell = (lesson: string, student: string) => {
    const k = key(lesson, student);
    let c = maps.get(k);
    if (!c) maps.set(k, (c = { grades: [] }));
    return c;
  };
  for (const a of grid.attendance) cell(a.lesson, a.student).attendance = a;
  for (const g of grid.grades) cell(g.lesson, g.student).grades.push(g);
  return maps;
}

type RowProps = {
  student: RowStudent;
  row: number;
  lessons: GridLesson[];
  maps: Maps;
  grid: Grid;
  selectedCol: number;
  buffer: string;
  weekStarts: Set<number>;
  onSelect: (row: number, col: number) => void;
};

const GridRow = memo(function GridRow({
  student,
  row,
  lessons,
  maps,
  grid,
  selectedCol,
  buffer,
  weekStarts,
  onSelect,
}: RowProps) {
  const stats = student.stats;
  const average = stats.average === null ? null : Number(stats.average);
  return (
    <tr>
      <th scope="row" className={styles.nameCell}>
        {student.short_name}
      </th>
      {lessons.map((lesson, col) => {
        const member = memberOn(student, lesson.date);
        const cell = maps.get(key(lesson.id, student.id));
        const selected = col === selectedCol;
        const classes = [
          styles.cell,
          weekStarts.has(col) && styles.weekStart,
          lesson.date === grid.today && styles.todayCell,
          !member && styles.outside,
          (!lesson.editable || !member) && styles.locked,
          selected && styles.selected,
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <td
            key={lesson.id}
            id={`cell-${row}-${col}`}
            role="gridcell"
            aria-selected={selected}
            className={classes}
            title={
              !member
                ? t("journal.notMember")
                : lesson.locked === "window"
                  ? t("journal.lockedHint")
                  : undefined
            }
            onClick={() => onSelect(row, col)}
          >
            {member ? (
              <span className={styles.cellContent}>
                {cell?.attendance && cell.attendance.status !== "present" && (
                  <span className={styles[`mark_${cell.attendance.status}`]}>
                    {mark(cell.attendance.status)}
                  </span>
                )}
                {cell?.grades.map((g) => (
                  <span
                    key={g.id}
                    className={isLow(g.value, grid.rules) ? styles.low : styles.grade}
                  >
                    {g.value}
                  </span>
                ))}
                {selected && buffer && <span className={styles.buffer}>{buffer}</span>}
              </span>
            ) : (
              <span aria-hidden="true">·</span>
            )}
          </td>
        );
      })}
      <td
        className={`${styles.summary} ${average !== null && average < Number(grid.rules.low_below) ? styles.low : ""}`}
      >
        {stats.average ?? "—"}
      </td>
      <td className={styles.summary}>
        {stats.attendance_percent === null
          ? "—"
          : `${Math.round(Number(stats.attendance_percent))}%`}
      </td>
      <td
        className={styles.summary}
        title={stats.excused ? `${t("attendance.excused")}: ${stats.excused}` : undefined}
      >
        {stats.absent + stats.excused}
      </td>
    </tr>
  );
});

function TopicsTab({ grid, base }: { grid: Grid; base: string }) {
  return (
    <table className={styles.topics}>
      <thead>
        <tr>
          <th scope="col">{t("journal.date")}</th>
          <th scope="col">{t("journal.type")}</th>
          <th scope="col">{t("journal.topic")}</th>
          <th scope="col">{t("journal.homework")}</th>
        </tr>
      </thead>
      <tbody>
        {grid.lessons.map((lesson) => (
          <tr key={lesson.id}>
            <td className="mono">
              <Link to={`${base}/lessons/${lesson.id}`}>{formatDate(lesson.date)}</Link>
            </td>
            <td>{lesson.lesson_type_short ?? "—"}</td>
            <td>{lesson.topic || "—"}</td>
            <td className={styles.homework}>{lesson.homework || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const TAB_LABELS = {
  grades: "journal.tabGrades",
  topics: "journal.tabTopics",
  reviews: "journal.tabReviews",
} as const;

/** «Журнал»: students × lessons with keyboard input (SPEC §7.3). */
export function JournalPage() {
  const me = useMe();
  const isAdmin = me.data?.active_role === "admin";
  const base = journalBase(me.data?.active_role);
  const [params, setParams] = useSearchParams();
  const courses = useJournalCourses();
  const course = params.get("course") || courses.data?.[0]?.id;
  const term = params.get("term") || undefined;
  const rawTab = params.get("tab");
  const tab = rawTab === "topics" || rawTab === "reviews" ? rawTab : "grades";
  const terms = useTerms(course);
  const grid = useGrid(course, term);
  const { state, perform, retry, undo, busy } = useSave();
  const [picked, setPicked] = useState<{ grid: string; row: number; col: number } | null>(null);
  const [buffer, setBuffer] = useState("");
  const [hint, setHint] = useState("");
  const [reason, setReason] = useState("");
  const [askReason, setAskReason] = useState<((why: string) => void) | null>(null);
  const [reasonDraft, setReasonDraft] = useState("");
  const [details, setDetails] = useState<{ lesson: GridLesson; student: RowStudent } | null>(null);
  const tableRef = useRef<HTMLTableElement>(null);

  const data = grid.data;
  const gridKey = data ? `${data.course.id}:${data.period_from}:${data.period_to}` : "";
  // Start on today's column (or the last lesson before it) until the user picks a cell.
  const startCol = useMemo(() => {
    let idx = 0;
    data?.lessons.forEach((l, i) => {
      if (l.date <= data.today) idx = i;
    });
    return idx;
  }, [data]);
  const sel = picked && picked.grid === gridKey ? picked : { grid: gridKey, row: 0, col: startCol };
  const setSel = (update: (s: { row: number; col: number }) => { row: number; col: number }) =>
    setPicked({ grid: gridKey, ...update(sel) });
  const maps = useMemo(() => (data ? buildMaps(data) : new Map()), [data]);
  const weekStarts = useMemo(() => {
    const set = new Set<number>();
    data?.lessons.forEach((lesson, i) => {
      const prev = data.lessons[i - 1];
      if (
        i > 0 &&
        prev &&
        (isoWeekday(lesson.date) <= isoWeekday(prev.date) || lesson.date >= addDays(prev.date, 7))
      )
        set.add(i);
    });
    return set;
  }, [data]);

  const setParam = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    if (name === "course") next.delete("term");
    setParams(next, { replace: true });
  };

  if (courses.isPending) return <RuledSkeleton rows={6} />;
  if (!courses.data?.length) return <EmptyState text={t("journal.noCourses")} />;

  const lessons = data?.lessons ?? [];
  const students = data?.students ?? [];
  const current = () => {
    const lesson = lessons[sel.col];
    const student = students[sel.row];
    if (!lesson || !student) return null;
    return { lesson, student, cell: maps.get(key(lesson.id, student.id)) as Cell | undefined };
  };

  /** Runs `fn` if the cell may be edited; asks for a reason when the window is closed. */
  const guarded = (fn: (reasonText: string) => void) => {
    const target = current();
    if (!target) return;
    if (!memberOn(target.student, target.lesson.date)) return setHint(t("journal.notMember"));
    if (!target.lesson.editable) {
      return setHint(
        target.lesson.locked === "future" ? t("journal.futureHint") : t("journal.lockedHint"),
      );
    }
    if (target.lesson.needs_reason && !reason.trim()) {
      setReasonDraft("");
      // The action runs with the reason typed into the dialog, not the one at this moment.
      setAskReason(() => fn);
      return;
    }
    fn(reason);
  };

  const onKey = (event: KeyboardEvent<HTMLTableElement>) => {
    if (!data) return;
    const move = (dr: number, dc: number) => {
      event.preventDefault();
      setBuffer("");
      setHint("");
      setSel((s) => ({
        row: Math.min(Math.max(0, s.row + dr), students.length - 1),
        col: Math.min(Math.max(0, s.col + dc), lessons.length - 1),
      }));
    };
    if (event.key === "ArrowUp") return move(-1, 0);
    if (event.key === "ArrowDown") return move(1, 0);
    if (event.key === "ArrowLeft") return move(0, -1);
    if (event.key === "ArrowRight") return move(0, 1);
    if (/^\d$/.test(event.key)) {
      event.preventDefault();
      setBuffer((b) => (b + event.key).slice(0, 3));
      return;
    }
    const target = current();
    if (!target) return;
    if (event.key === "Enter") {
      event.preventDefault();
      if (!buffer) return setDetails({ lesson: target.lesson, student: target.student });
      const value = Number(buffer);
      const [min, max] = SCALE_RANGE[data.rules.scale] ?? [0, 100];
      setBuffer("");
      if (value < min || value > max) return setHint(t("journal.outOfRange", { min, max }));
      return guarded(
        (why) => void perform(addGradeAction(target.lesson, target.student.id, value, why)),
      );
    }
    if (event.key === "Escape") {
      if (buffer) return setBuffer("");
      tableRef.current?.blur();
      return;
    }
    if (event.key === "Backspace" && buffer) {
      event.preventDefault();
      return setBuffer((b) => b.slice(0, -1));
    }
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      const own = [...(target.cell?.grades ?? [])].reverse().find((g) => g.mine || isAdmin);
      if (own) guarded((why) => void perform(deleteGradeAction(own, why)));
      return;
    }
    const status = statusFromKey(event);
    if (status === "absent") {
      event.preventDefault();
      const previous = target.cell?.attendance;
      guarded(
        (why) =>
          void perform({
            run: () =>
              journalApi.setAttendance(target.lesson.id, target.student.id, {
                status: "absent",
                version: previous?.version ?? null,
                reason: why,
              }),
            undo: (result) => {
              const saved = result as Attendance;
              return previous
                ? () =>
                    journalApi.setAttendance(target.lesson.id, target.student.id, {
                      status: previous.status,
                      version: saved.version,
                      reason: why,
                    })
                : () =>
                    journalApi.clearAttendance(target.lesson.id, target.student.id, {
                      version: saved.version,
                      reason: why,
                    });
            },
          }),
      );
    }
  };

  const courseOptions = (courses.data ?? []).map((c) => ({
    value: c.id,
    label: `${c.group_name} · ${c.subject_name}${isAdmin ? ` · ${c.teacher_name}` : ""}`,
  }));
  const termOptions = [
    { value: "", label: t("journal.period") },
    ...(terms.data ?? []).map((x) => ({
      value: x.id,
      label: `${x.name} (${formatDate(x.starts_on)}–${formatDate(x.ends_on)})`,
    })),
    { value: "year", label: t("journal.wholeYear") },
  ];
  const detailCell = details ? maps.get(key(details.lesson.id, details.student.id)) : undefined;

  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("journal.title")}</h1>
        <SaveStatus state={state} retry={retry} undo={undo} />
      </div>
      <div className={styles.toolbar}>
        <SelectField
          label={t("journal.course")}
          value={course ?? ""}
          onChange={(e) => setParam("course", e.target.value)}
          options={courseOptions}
        />
        <SelectField
          label={t("journal.period")}
          value={term ?? ""}
          onChange={(e) => setParam("term", e.target.value)}
          options={termOptions}
        />
      </div>
      <div className={styles.tabs} role="tablist">
        {(["grades", "topics", "reviews"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            className={styles.tab}
            onClick={() => setParam("tab", value === "grades" ? "" : value)}
          >
            {t(TAB_LABELS[value])}
          </button>
        ))}
      </div>

      {tab === "reviews" && course ? (
        <ReviewsTab course={course} term={term} />
      ) : grid.isPending ? (
        <RuledSkeleton rows={10} />
      ) : grid.error || !data ? (
        <p className={styles.error}>{errorMessage(grid.error)}</p>
      ) : lessons.length === 0 ? (
        <EmptyState text={t("journal.noLessons")} />
      ) : tab === "topics" ? (
        <TopicsTab grid={data} base={base} />
      ) : (
        <>
          <p className={styles.note}>{t("journal.keyboardHint")}</p>
          <p className={styles.hint} role="status" aria-live="polite">
            {hint}
          </p>
          <div className={styles.scroller}>
            <table
              ref={tableRef}
              className={styles.grid}
              // ARIA allows role="grid" on <table> (WAI-ARIA APG data grid pattern).
              // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role
              role="grid"
              tabIndex={0}
              aria-label={`${data.course.group_name} · ${data.course.subject_name}`}
              aria-activedescendant={`cell-${sel.row}-${sel.col}`}
              onKeyDown={onKey}
            >
              <thead>
                <tr>
                  <th scope="col" className={styles.nameCell}>
                    {t("journal.student")}
                  </th>
                  {lessons.map((lesson, col) => (
                    <th
                      key={lesson.id}
                      scope="col"
                      title={lesson.topic || undefined}
                      className={[
                        styles.dateHead,
                        weekStarts.has(col) && styles.weekStart,
                        lesson.date === data.today && styles.todayHead,
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      <Link to={`${base}/lessons/${lesson.id}`} tabIndex={-1}>
                        {lesson.date.slice(8, 10)}.{lesson.date.slice(5, 7)}
                      </Link>
                      <span className={styles.dateType}>{lesson.lesson_type_short ?? ""}</span>
                    </th>
                  ))}
                  <th scope="col" className={styles.summary}>
                    {t("journal.average")}
                  </th>
                  <th scope="col" className={styles.summary}>
                    {t("journal.attendance")}
                  </th>
                  <th scope="col" className={styles.summary}>
                    {t("journal.absences")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {students.map((student, row) => (
                  <GridRow
                    key={student.id}
                    student={student}
                    row={row}
                    lessons={lessons}
                    maps={maps}
                    grid={data}
                    selectedCol={row === sel.row ? sel.col : -1}
                    buffer={row === sel.row ? buffer : ""}
                    weekStarts={weekStarts}
                    onSelect={(r, c) => {
                      setSel(() => ({ row: r, col: c }));
                      setBuffer("");
                      setHint("");
                      tableRef.current?.focus();
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Dialog
        open={details !== null}
        onOpenChange={(o) => !o && setDetails(null)}
        title={details ? `${details.student.full_name} · ${formatDate(details.lesson.date)}` : ""}
      >
        {details && data && (
          <div className={styles.form}>
            <StudentEditor
              lesson={details.lesson}
              rules={data.rules}
              workTypes={data.work_types}
              student={details.student}
              attendance={detailCell?.attendance}
              grades={detailCell?.grades ?? []}
              reason={reason}
              isAdmin={isAdmin}
              busy={busy}
              perform={perform}
            />
            {details.lesson.needs_reason && (
              <TextField
                label={t("journal.reasonField")}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            )}
            <DialogActions>
              <Link to={`${base}/lessons/${details.lesson.id}`}>{t("journal.openLesson")}</Link>
              <Button onClick={() => setDetails(null)}>{t("common.close")}</Button>
            </DialogActions>
          </div>
        )}
      </Dialog>

      <Dialog
        open={askReason !== null}
        onOpenChange={(o) => !o && setAskReason(null)}
        title={t("journal.reasonTitle")}
        description={t("journal.lockedHint")}
      >
        <form
          className={styles.form}
          onSubmit={(e) => {
            e.preventDefault();
            setReason(reasonDraft);
            askReason?.(reasonDraft);
            setAskReason(null);
            tableRef.current?.focus();
          }}
        >
          <TextField
            label={t("journal.reasonField")}
            value={reasonDraft}
            onChange={(e) => setReasonDraft(e.target.value)}
          />
          <DialogActions>
            <Button type="submit" variant="primary" disabled={!reasonDraft.trim()}>
              {t("journal.save")}
            </Button>
            <Button onClick={() => setAskReason(null)}>{t("common.cancel")}</Button>
          </DialogActions>
        </form>
      </Dialog>
    </section>
  );
}
