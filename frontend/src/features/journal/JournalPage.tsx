import { ChevronLeft, ChevronRight, MessageSquare } from "lucide-react";
import { memo, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { useMe } from "@/features/auth/api";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { addDays, formatDate, isoWeekday, monthName, weekdayShort } from "@/shared/lib/week";
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
import { CellDialog } from "./CellDialog";
import styles from "./Journal.module.css";
import { journalBase } from "./paths";
import {
  addGradeAction,
  attendanceAction,
  deleteGradeAction,
  mark,
  statusFromKey,
} from "./actions";
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

/** Runs of lessons in one month: «Ноябрь» over its columns. */
function monthRuns(lessons: GridLesson[]): { month: string; count: number }[] {
  const runs: { month: string; count: number }[] = [];
  for (const lesson of lessons) {
    const month = lesson.date.slice(0, 7);
    const last = runs.at(-1);
    if (last && last.month === month) last.count += 1;
    else runs.push({ month, count: 1 });
  }
  return runs;
}

/** The remark of a cell: the grade's «why» or the comment of an absence. */
function remarkOf(cell: Cell | undefined): string {
  if (!cell) return "";
  return [cell.attendance?.comment, ...cell.grades.map((g) => g.comment)]
    .filter(Boolean)
    .join(" · ");
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
      <td className={styles.numCell}>{row + 1}</td>
      <th scope="row" className={styles.nameCell} title={student.full_name}>
        {student.full_name}
      </th>
      <td
        className={`${styles.summary} ${styles.sumAverage} ${average !== null && average < Number(grid.rules.low_below) ? styles.low : ""}`}
      >
        {stats.average ?? "·"}
      </td>
      <td className={`${styles.summary} ${styles.sumAttendance}`}>
        {stats.attendance_percent === null
          ? "·"
          : `${Math.round(Number(stats.attendance_percent))}%`}
      </td>
      <td
        className={`${styles.summary} ${styles.sumAbsences}`}
        title={stats.excused ? `${t("attendance.excused")}: ${stats.excused}` : undefined}
      >
        {stats.absent + stats.excused}
      </td>
      {lessons.map((lesson, col) => {
        const member = memberOn(student, lesson.date);
        const cell = maps.get(key(lesson.id, student.id));
        const selected = col === selectedCol;
        const remark = member ? remarkOf(cell) : "";
        const status = cell?.attendance?.status;
        // Stage 19: only «н» is shown; an excused absence (older records) reads as «н» too.
        const marked = status === "absent" || status === "excused";
        const empty = !marked && !cell?.grades.length && !(selected && buffer);
        const classes = [
          styles.cell,
          weekStarts.has(col) && styles.weekStart,
          lesson.date === grid.today && styles.todayCell,
          !member && styles.outside,
          (!lesson.editable || !member) && styles.locked,
          remark && styles.hasRemark,
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
                : remark ||
                  (status === "late"
                    ? t("journal.lateTitle", { minutes: cell?.attendance?.late_minutes ?? "?" })
                    : "") ||
                  (lesson.locked === "window"
                    ? t("journal.lockedHint")
                    : lesson.locked === "future"
                      ? t("journal.futureHint")
                      : undefined)
            }
            onClick={() => onSelect(row, col)}
          >
            {member && !empty ? (
              <span className={styles.cellContent}>
                {marked && status && <span className={styles.cellAbsent}>{mark("absent")}</span>}
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
              <span className={styles.dot} aria-hidden="true">
                ·
              </span>
            )}
          </td>
        );
      })}
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

/** The groups as one pill strip with arrows at the ends, like the eDonish class strip. */
function GroupStrip({
  groups,
  chosen,
  onPick,
}: {
  groups: string[];
  chosen: string | undefined;
  onPick: (name: string) => void;
}) {
  const strip = useRef<HTMLDivElement>(null);
  const scroll = (direction: number) =>
    strip.current?.scrollBy?.({
      left: direction * strip.current.clientWidth * 0.8,
      behavior: "smooth",
    });
  return (
    <div className={styles.stripFrame}>
      <button
        type="button"
        className={styles.stripArrow}
        aria-label={t("journal.groupsBack")}
        onClick={() => scroll(-1)}
      >
        <ChevronLeft size={20} strokeWidth={1.5} aria-hidden="true" />
      </button>
      <div ref={strip} className={styles.strip} role="group" aria-label={t("journal.group")}>
        {groups.map((name) => (
          <button
            key={name}
            type="button"
            className={styles.stripItem}
            aria-pressed={chosen === name}
            onClick={() => onPick(name)}
          >
            {name}
          </button>
        ))}
      </div>
      <button
        type="button"
        className={styles.stripArrow}
        aria-label={t("journal.groupsForward")}
        onClick={() => scroll(1)}
      >
        <ChevronRight size={20} strokeWidth={1.5} aria-hidden="true" />
      </button>
    </div>
  );
}

/** «Журнал»: students × lessons, after the eDonish journal (stage 18). */
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
  const { state, perform, retry, undo } = useSave();
  const [picked, setPicked] = useState<{ grid: string; row: number; col: number } | null>(null);
  const [buffer, setBuffer] = useState("");
  const [hint, setHint] = useState("");
  const [reason, setReason] = useState("");
  const [askReason, setAskReason] = useState<((why: string) => void) | null>(null);
  const [reasonDraft, setReasonDraft] = useState("");
  const [editing, setEditing] = useState<{ lesson: GridLesson; student: RowStudent } | null>(null);
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
  const months = useMemo(() => monthRuns(data?.lessons ?? []), [data]);

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
  const at = (row: number, col: number) => {
    const lesson = lessons[col];
    const student = students[row];
    if (!lesson || !student) return null;
    return { lesson, student, cell: maps.get(key(lesson.id, student.id)) as Cell | undefined };
  };
  const current = () => at(sel.row, sel.col);

  /** Says why a cell cannot be changed; empty when it can. */
  const lockOf = (lesson: GridLesson, student: RowStudent) =>
    !memberOn(student, lesson.date)
      ? t("journal.notMember")
      : lesson.editable
        ? ""
        : lesson.locked === "future"
          ? t("journal.futureHint")
          : t("journal.lockedHint");

  /** The cell window: points or «н» and a remark. */
  const openCell = (row: number, col: number) => {
    const target = at(row, col);
    if (!target) return;
    const locked = lockOf(target.lesson, target.student);
    if (locked) return setHint(locked);
    setHint("");
    setEditing({ lesson: target.lesson, student: target.student });
  };

  /** Runs `fn` if the cell may be edited; asks for a reason when the window is closed. */
  const guarded = (fn: (reasonText: string) => void) => {
    const target = current();
    if (!target) return;
    const locked = lockOf(target.lesson, target.student);
    if (locked) return setHint(locked);
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
      if (!buffer) return openCell(sel.row, sel.col);
      const value = Number(buffer);
      const [min, max] = SCALE_RANGE[data.rules.scale] ?? [0, 100];
      setBuffer("");
      if (value < min || value > max) return setHint(t("journal.outOfRange", { min, max }));
      return guarded(
        (why) =>
          void perform(
            addGradeAction(
              target.lesson,
              target.student.id,
              value,
              why,
              undefined,
              target.student.short_name,
            ),
          ),
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
          void perform(
            attendanceAction(
              target.lesson,
              target.student.id,
              previous,
              { status: "absent" },
              why,
              target.student.short_name,
            ),
          ),
      );
    }
  };

  // After the eDonish journal: first the group, then its subject, then the period.
  const allCourses = courses.data ?? [];
  const groups = [...new Set(allCourses.map((c) => c.group_name))];
  const chosen = allCourses.find((c) => c.id === course);
  const groupCourses = allCourses.filter((c) => c.group_name === chosen?.group_name);
  const pickGroup = (name: string) => {
    const same = allCourses.find(
      (c) => c.group_name === name && c.subject_name === chosen?.subject_name,
    );
    const first = same ?? allCourses.find((c) => c.group_name === name);
    if (first) setParam("course", first.id);
  };
  const subjectOptions = groupCourses.map((c) => ({
    value: c.id,
    label: `${c.subject_name}${isAdmin ? ` · ${c.teacher_name}` : ""}`,
  }));
  const termOptions = [
    { value: "", label: t("journal.period") },
    ...(terms.data ?? []).map((x) => ({ value: x.id, label: x.name })),
    { value: "year", label: t("journal.wholeYear") },
  ];
  const shownTerm =
    term ?? terms.data?.find((x) => data && x.starts_on === data.period_from)?.id ?? "";
  const editCell = editing ? maps.get(key(editing.lesson.id, editing.student.id)) : undefined;

  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1 className={styles.crumb}>{t("journal.title")}</h1>
        <SaveStatus state={state} retry={retry} undo={undo} />
      </div>
      {groups.length > 0 && (
        <GroupStrip groups={groups} chosen={chosen?.group_name} onPick={pickGroup} />
      )}
      <div className={styles.toolbar}>
        <SelectField
          className={styles.pillSelect}
          label={t("journal.subject")}
          value={course ?? ""}
          onChange={(e) => setParam("course", e.target.value)}
          options={subjectOptions}
        />
        <SelectField
          className={styles.pillSelect}
          label={t("journal.period")}
          value={shownTerm}
          onChange={(e) => setParam("term", e.target.value)}
          options={termOptions}
        />
      </div>
      <div className={styles.teacherRow}>
        {chosen && (
          <p className={styles.teacherLine}>
            {t("journal.teacherLine", { name: chosen.teacher_name })}
          </p>
        )}
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
          <p className={styles.hint} role="status" aria-live="polite">
            {hint}
          </p>
          <p id="journal-keys" className="visually-hidden">
            {t("journal.keyboardHint")}
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
              aria-describedby="journal-keys"
              aria-activedescendant={`cell-${sel.row}-${sel.col}`}
              onKeyDown={onKey}
            >
              <thead>
                <tr className={styles.headMonth}>
                  <th scope="col" rowSpan={4} className={styles.numCell}>
                    №
                  </th>
                  <th scope="col" rowSpan={4} className={styles.nameCell}>
                    {t("journal.studentName")}
                  </th>
                  <th scope="col" rowSpan={4} className={`${styles.summary} ${styles.sumAverage}`}>
                    <span className={styles.vertical}>{t("journal.averageLong")}</span>
                  </th>
                  <th
                    scope="col"
                    rowSpan={4}
                    className={`${styles.summary} ${styles.sumAttendance}`}
                  >
                    <span className={styles.vertical}>{t("journal.attendanceLong")}</span>
                  </th>
                  <th scope="col" rowSpan={4} className={`${styles.summary} ${styles.sumAbsences}`}>
                    <span className={styles.vertical}>{t("journal.absences")}</span>
                  </th>
                  {months.map((m) => (
                    <th
                      key={m.month}
                      scope="colgroup"
                      colSpan={m.count}
                      className={styles.monthHead}
                    >
                      {monthName(`${m.month}-01`)}
                    </th>
                  ))}
                </tr>
                <tr className={styles.headDay}>
                  {lessons.map((lesson, col) => (
                    <th
                      key={lesson.id}
                      scope="col"
                      className={[
                        styles.dateHead,
                        weekStarts.has(col) && styles.weekStart,
                        lesson.date === data.today && styles.todayHead,
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      {Number(lesson.date.slice(8, 10))}
                    </th>
                  ))}
                </tr>
                <tr className={styles.headWeekday}>
                  {lessons.map((lesson, col) => (
                    <th
                      key={lesson.id}
                      scope="col"
                      className={[
                        styles.weekdayHead,
                        weekStarts.has(col) && styles.weekStart,
                        lesson.date === data.today && styles.todayHead,
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      {weekdayShort(lesson.date)}
                    </th>
                  ))}
                </tr>
                <tr className={styles.headTopic}>
                  {lessons.map((lesson, col) => (
                    <th
                      key={lesson.id}
                      scope="col"
                      className={[
                        styles.topicHead,
                        weekStarts.has(col) && styles.weekStart,
                        lesson.date === data.today && styles.todayHead,
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      <Link
                        to={`${base}/lessons/${lesson.id}`}
                        tabIndex={-1}
                        className={lesson.topic ? styles.topicLink : styles.topicLinkEmpty}
                        title={lesson.topic || t("journal.noTopicYet")}
                        aria-label={t("journal.lessonOn", { date: formatDate(lesson.date) })}
                      >
                        <MessageSquare size={15} strokeWidth={1.5} aria-hidden="true" />
                      </Link>
                    </th>
                  ))}
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
                      tableRef.current?.focus();
                      openCell(r, c);
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {editing && data && (
        <CellDialog
          key={`${editing.lesson.id}:${editing.student.id}`}
          lesson={editing.lesson}
          student={editing.student}
          subject={data.course.subject_name}
          attendance={editCell?.attendance}
          grades={editCell?.grades ?? []}
          rules={data.rules}
          isAdmin={isAdmin}
          reason={reason}
          onReason={setReason}
          perform={perform}
          state={state}
          onClose={() => {
            setEditing(null);
            tableRef.current?.focus();
          }}
        />
      )}

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
