import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ME_STUDENT, mockApi } from "@/test/api-mock";
import { renderRoutes, withQuery } from "@/test/render";

import { statusFromKey } from "./actions";
import type { Grid, Rules } from "./api";
import { JournalPage } from "./JournalPage";
import { OfflineBar } from "./OfflineBar";
import { resetQueue } from "./offlineQueue";
import { StudentEditor } from "./StudentEditor";

const RULES: Rules = { scale: "100", low_below: "50.00", max_grades: 3, edit_window_days: 7 };
const LESSON = { id: "l1", editable: true, needs_reason: false };
const STUDENT = { id: "s1", short_name: "Алиев Ф.", full_name: "Алиев Фарход" };
const ME_TEACHER = { ...ME_STUDENT, roles: ["teacher"], active_role: "teacher" };

describe("statusFromKey", () => {
  it("understands Б/О/Н/У on both layouts", () => {
    expect(statusFromKey({ key: "н", code: "KeyY" })).toBe("absent");
    expect(statusFromKey({ key: "y", code: "KeyY" })).toBe("absent");
    expect(statusFromKey({ key: "Б", code: "Comma" })).toBe("present");
    expect(statusFromKey({ key: "x", code: "KeyX" })).toBeUndefined();
  });
});

describe("StudentEditor", () => {
  function setup(extra: Partial<Parameters<typeof StudentEditor>[0]> = {}) {
    const perform = vi.fn().mockResolvedValue(true);
    withQuery(
      <StudentEditor
        lesson={LESSON}
        rules={RULES}
        workTypes={[]}
        student={STUDENT}
        grades={[]}
        reason=""
        isAdmin={false}
        busy={false}
        perform={perform}
        {...extra}
      />,
    );
    return perform;
  }

  it("defaults to «был» and switches to «н» on tap (stage 19: no lateness)", async () => {
    const perform = setup();
    const toggle = screen.getByRole("button", { name: /Посещаемость: был/ });
    expect(toggle).toHaveTextContent("был");
    const fetchMock = mockApi({
      "PUT /journal/lessons/l1/attendance/s1": { body: { version: 1 } },
    }).fetchMock;
    await userEvent.click(toggle);
    await perform.mock.calls[0]![0].run();
    expect(JSON.parse(fetchMock.mock.calls[0]![1]!.body as string).status).toBe("absent");
  });

  it("sets the status by key", async () => {
    const perform = setup();
    const toggle = screen.getByRole("button", { name: /Посещаемость/ });
    toggle.focus();
    fireEvent.keyDown(toggle, { key: "н", code: "KeyY" });
    expect(perform).toHaveBeenCalledTimes(1);
  });

  it("disables grade input for absent students", () => {
    setup({
      attendance: {
        id: "a1",
        lesson: "l1",
        student: "s1",
        status: "absent",
        late_minutes: null,
        comment: "",
        version: 1,
      },
    });
    expect(screen.queryByLabelText("Оценка для Алиев Ф.")).not.toBeInTheDocument();
  });

  it("checks the range while typing and submits on Enter", async () => {
    const perform = setup();
    const input = screen.getByLabelText("Оценка для Алиев Ф.");
    await userEvent.type(input, "105");
    expect(input).toHaveAttribute("aria-invalid", "true");
    await userEvent.clear(input);
    await userEvent.type(input, "87{Enter}");
    expect(perform).toHaveBeenCalledTimes(1);
  });

  it("shows value buttons for small scales", async () => {
    const perform = setup({ rules: { ...RULES, scale: "5" } });
    const group = screen.getByRole("group", { name: "Оценка для Алиев Ф." });
    expect(
      within(group)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["2", "3", "4", "5"]);
    await userEvent.click(within(group).getByRole("button", { name: "4" }));
    expect(perform).toHaveBeenCalledTimes(1);
  });

  it("does not let others edit a colleague's grade", () => {
    setup({
      grades: [
        {
          id: "g1", lesson: "l1", student: "s1", value: 40, work_type: "w", weight: "1.00",
          comment: "", position: 1, mine: false, author_name: "Ким С.", version: 1,
        },
      ],
    }); // prettier-ignore
    const chip = screen.getByRole("button", { name: "40" });
    expect(chip).toBeDisabled();
    expect(chip).toHaveAttribute("title", expect.stringContaining("Ким С."));
  });
});

function grid(overrides: Partial<Grid> = {}): Grid {
  return {
    course: { id: "c1", group_name: "11-М", subject_name: "Математика", teacher_name: "Юсупов Т.", year_name: "2026/2027", scale: "100" },
    period_from: "2026-11-01",
    period_to: "2026-12-31",
    today: "2026-11-16",
    rules: RULES,
    lessons: [
      { id: "old", date: "2026-11-02", start_time: "14:00:00", lesson_type: null, lesson_type_short: "Пр", lesson_type_name: "Практика",
        topic: "Модуль", homework: "", status: "conducted", version: 1, editable: false, needs_reason: false, locked: "window" },
      { id: "l1", date: "2026-11-16", start_time: "14:00:00", lesson_type: null, lesson_type_short: "Пр", lesson_type_name: "Практика",
        topic: "Логарифмы", homework: "", status: "planned", version: 1, editable: true, needs_reason: false, locked: null },
    ],
    students: [
      { id: "s1", short_name: "Алиев Ф.", full_name: "Алиев Фарход", periods: [{ start: "2026-09-01", end: null }],
        stats: { average: "45.50", grades: 2, attendance_percent: "75.00", present: 3, late: 0, absent: 1, excused: 0, eligible: 4 } },
    ],
    attendance: [],
    grades: [],
    work_types: [],
    ...overrides,
  } as Grid; // prettier-ignore
}

describe("JournalPage", () => {
  const routes = [{ path: "/teacher/journal", element: <JournalPage /> }];

  it("enters a grade with the keyboard on today's column", async () => {
    const posted: unknown[] = [];
    mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /journal/courses": {
        body: [
          {
            id: "c1",
            group_name: "11-М",
            subject_name: "Математика",
            teacher_name: "Юсупов Т.",
            year: "y",
          },
        ],
      },
      "GET /journal/courses/c1/terms": { body: [] },
      "GET /journal/courses/c1": { body: grid() },
      "POST /journal/lessons/l1/grades": (init) => {
        posted.push(JSON.parse(init.body as string));
        return { status: 201, body: { id: "g1", version: 1 } };
      },
    });
    renderRoutes(routes, "/teacher/journal");
    const table = await screen.findByRole("grid");
    expect(screen.getByText("45.50")).toHaveClass("low");
    table.focus();
    fireEvent.keyDown(table, { key: "8" });
    fireEvent.keyDown(table, { key: "7" });
    expect(screen.getByText("87")).toBeInTheDocument();
    fireEvent.keyDown(table, { key: "Enter" });
    await waitFor(() =>
      expect(posted).toEqual([
        { student: "s1", value: 87, work_type: null, reason: "", client_key: expect.any(String) },
      ]),
    );
  });

  it("refuses edits in a locked column and says why", async () => {
    const { calls } = mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /journal/courses": {
        body: [
          {
            id: "c1",
            group_name: "11-М",
            subject_name: "Математика",
            teacher_name: "Ю",
            year: "y",
          },
        ],
      },
      "GET /journal/courses/c1/terms": { body: [] },
      "GET /journal/courses/c1": { body: grid() },
    });
    renderRoutes(routes, "/teacher/journal");
    const table = await screen.findByRole("grid");
    table.focus();
    fireEvent.keyDown(table, { key: "ArrowLeft" });
    fireEvent.keyDown(table, { key: "н", code: "KeyY" });
    expect(await screen.findByText("Изменить может администратор")).toBeInTheDocument();
    expect(calls.some((c) => c.method !== "GET")).toBe(false);
  });

  it("switches to the topics tab", async () => {
    mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /journal/courses": {
        body: [
          {
            id: "c1",
            group_name: "11-М",
            subject_name: "Математика",
            teacher_name: "Ю",
            year: "y",
          },
        ],
      },
      "GET /journal/courses/c1/terms": { body: [] },
      "GET /journal/courses/c1": { body: grid() },
    });
    renderRoutes(routes, "/teacher/journal");
    await userEvent.click(await screen.findByRole("tab", { name: "Темы" }));
    expect(screen.getByText("Логарифмы")).toBeInTheDocument();
  });
});

describe("the cell window (stage 18)", () => {
  const routes = [{ path: "/teacher/journal", element: <JournalPage /> }];
  const COURSES = {
    body: [
      { id: "c1", group_name: "11-М", subject_name: "Математика", teacher_name: "Ю", year: "y" },
    ],
  };
  beforeEach(resetQueue);

  it("gives points with a remark: why the grade is low", async () => {
    const { calls } = mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /journal/courses": COURSES,
      "GET /journal/courses/c1/terms": { body: [] },
      "GET /journal/courses/c1": { body: grid() },
      "POST /journal/lessons/l1/grades": { status: 201, body: { id: "g1", version: 1 } },
    });
    renderRoutes(routes, "/teacher/journal");
    const table = await screen.findByRole("grid");
    // Head: the month, the vertical summary columns; a dot in an empty cell.
    expect(within(table).getByText("ноябрь")).toBeInTheDocument();
    expect(within(table).getByText("Средний балл")).toBeInTheDocument();
    await userEvent.click(document.getElementById("cell-0-1")!);
    const dialog = await screen.findByRole("dialog", { name: "Алиев Фарход" });
    await userEvent.type(within(dialog).getByLabelText(/Баллы/), "35");
    await userEvent.type(within(dialog).getByLabelText("Замечание"), "Не решил задачи 3–5");
    await userEvent.click(within(dialog).getByRole("button", { name: "сохранить" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      student: "s1",
      value: 35,
      work_type: null,
      comment: "Не решил задачи 3–5",
      reason: "",
      client_key: expect.any(String),
    });
  });

  it("marks «н» with a remark; the student's own grade goes first", async () => {
    const { calls } = mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /journal/courses": COURSES,
      "GET /journal/courses/c1/terms": { body: [] },
      "GET /journal/courses/c1": {
        body: grid({
          grades: [
            { id: "g1", lesson: "l1", student: "s1", value: 70, work_type: "w", weight: "1.00",
              comment: "", position: 1, mine: true, author_name: "Ю", version: 2 },
          ],
        }),
      }, // prettier-ignore
      "POST /journal/grades/g1/delete": { body: { id: "g1", version: 3 } },
      "PUT /journal/lessons/l1/attendance/s1": {
        body: { id: "a1", lesson: "l1", student: "s1", status: "absent", late_minutes: null, comment: "Болел", version: 1 },
      }, // prettier-ignore
    });
    renderRoutes(routes, "/teacher/journal");
    await screen.findByRole("grid");
    await userEvent.click(document.getElementById("cell-0-1")!);
    const dialog = await screen.findByRole("dialog", { name: "Алиев Фарход" });
    expect(within(dialog).getByLabelText(/Баллы/)).toHaveValue("70");
    await userEvent.click(within(dialog).getByRole("button", { name: "Отсутствовал («н»)" }));
    expect(within(dialog).getByLabelText(/Баллы/)).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Замечание"), "Болел");
    await userEvent.click(within(dialog).getByRole("button", { name: "сохранить" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const writes = calls.filter((c) => c.method !== "GET");
    expect(writes.map((c) => c.path)).toEqual([
      "/journal/grades/g1/delete",
      "/journal/lessons/l1/attendance/s1",
    ]);
    expect(writes[1]?.body).toEqual({
      status: "absent",
      comment: "Болел",
      version: null,
      reason: "",
    });
  });

  it("does not open on a locked column and says why", async () => {
    mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /journal/courses": COURSES,
      "GET /journal/courses/c1/terms": { body: [] },
      "GET /journal/courses/c1": { body: grid() },
    });
    renderRoutes(routes, "/teacher/journal");
    await screen.findByRole("grid");
    await userEvent.click(document.getElementById("cell-0-0")!);
    expect(await screen.findByText("Изменить может администратор")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("ReviewsTab", () => {
  const routes = [{ path: "/teacher/journal", element: <JournalPage /> }];
  const term = { id: "t2", name: "Модуль 2", starts_on: "2026-11-01", ends_on: "2026-12-31" };
  const row = {
    student: "s1",
    full_name: "Алиев Фарход",
    text: "",
    author_name: "",
    updated_at: null,
    version: null,
  };

  function setup(extra: Record<string, unknown> = {}) {
    return mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /journal/courses": {
        body: [{ id: "c1", group_name: "11-М", subject_name: "Математика", teacher_name: "Ю", year: "y" }],
      },
      "GET /journal/courses/c1/terms": { body: [] },
      "GET /journal/courses/c1": { body: grid() },
      "GET /journal/courses/c1/reviews": {
        body: {
          term, editable: true, needs_reason: false, locked: null,
          closes_on: "2027-01-07", max_length: 600, rows: [row], ...extra,
        },
      },
      "PUT /journal/courses/c1/reviews/s1": (init) => ({
        body: { ...row, text: JSON.parse(init.body as string).text.trim(), author_name: "Юсупов Т.",
          updated_at: "2026-11-16T09:00:00Z", version: 1 },
      }),
    }); // prettier-ignore
  }

  it("saves a review when the field loses focus", async () => {
    const { calls } = setup();
    renderRoutes(routes, "/teacher/journal?tab=reviews");
    const field = await screen.findByLabelText("Алиев Фарход");
    await userEvent.type(field, "Сильная алгебра.");
    await userEvent.tab();
    expect(await screen.findByText(/Юсупов Т\., 16\.11\.2026/)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      term: "t2",
      text: "Сильная алгебра.",
      version: null,
      reason: "",
    });
  });

  it("is read-only for an assistant", async () => {
    setup({ editable: false, locked: "not_course_teacher" });
    renderRoutes(routes, "/teacher/journal?tab=reviews");
    expect(await screen.findByLabelText("Алиев Фарход")).toBeDisabled();
    expect(screen.getByText(/пишет основной преподаватель/)).toBeInTheDocument();
  });
});

describe("offline queue on the grid (stage 13)", () => {
  beforeEach(resetQueue); // versions remembered by the tests above
  afterEach(() => {
    vi.restoreAllMocks();
    resetQueue();
  });

  it("keeps a mark while there is no network and sends it when the network is back", async () => {
    const online = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    const { calls } = mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /journal/courses": {
        body: [{ id: "c1", group_name: "11-М", subject_name: "Математика", teacher_name: "Ю", year: "y" }],
      },
      "GET /journal/courses/c1/terms": { body: [] },
      "GET /journal/courses/c1": { body: grid() },
      "PUT /journal/lessons/l1/attendance/s1": {
        body: { id: "a1", lesson: "l1", student: "s1", status: "absent", late_minutes: null, comment: "", version: 1 },
      },
    }); // prettier-ignore
    renderRoutes(
      [
        {
          path: "/teacher/journal",
          element: (
            <>
              <OfflineBar />
              <JournalPage />
            </>
          ),
        },
      ],
      "/teacher/journal",
    );
    const table = await screen.findByRole("grid");
    table.focus();
    fireEvent.keyDown(table, { key: "н", code: "KeyY" });
    expect(await screen.findByText("Не отправлено: 1")).toBeInTheDocument();
    expect(screen.getByText("Алиев Ф. · отсутствовал")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PUT")).toBe(false);

    online.mockReturnValue(true);
    window.dispatchEvent(new Event("online"));
    await waitFor(() => expect(screen.queryByText("Не отправлено: 1")).not.toBeInTheDocument());
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      status: "absent",
      version: null,
      reason: "",
    });
  });
});
