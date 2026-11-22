import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Gate } from "@/app/Gate";
import { BRANDING, ME_STUDENT, mockApi } from "@/test/api-mock";
import { renderRoutes } from "@/test/render";

import { AttendancePage } from "./AttendancePage";
import { DiaryPage } from "./DiaryPage";
import { GradesPage } from "./GradesPage";

const LESSON = {
  id: "l1", date: "2026-11-16", start_time: "14:00:00", end_time: "15:30:00",
  subject_name: "Математика", subject_short: "Мат", group_name: "11-М", teacher_name: "Юсупов Тимур",
  room_name: "101", lesson_type_short: "Пр", lesson_type_name: "Практика", status: "conducted",
  cancel_reason: "", is_extra: false, is_moved: false, is_room_changed: false, is_substituted: false,
  planned_date: "2026-11-16", planned_start_time: "14:00:00", planned_end_time: "15:30:00", planned_room_name: "101",
  topic: "Логарифмы", homework: "№ 12–15", attendance: "late",
  grades: [{ id: "g1", value: 40, work_type_name: "Ответ на занятии", weight: "1.00", comment: "", low: true }],
}; // prettier-ignore

describe("DiaryPage", () => {
  it("shows the week as a spread with topics, homework, marks and grades", async () => {
    mockApi({
      "GET /student/diary": {
        body: { week_start: "2026-11-16", today: "2026-11-16", lessons: [LESSON] },
      },
    });
    renderRoutes(
      [{ path: "/student/diary", element: <DiaryPage /> }],
      "/student/diary?week=2026-11-16",
    );
    const monday = await screen.findByRole("region", { name: "пн, 16 ноября" });
    expect(within(monday).getByText("Логарифмы")).toBeInTheDocument();
    expect(within(monday).getByText(/№ 12–15/)).toBeInTheDocument();
    expect(within(monday).getByText(/оп/)).toBeInTheDocument();
    expect(within(monday).getByText("40")).toHaveClass("low");
    // Sunday is not shown when empty.
    expect(screen.queryByRole("region", { name: "вс, 22 ноября" })).not.toBeInTheDocument();
  });

  it("turns the page with a swipe", async () => {
    const { calls } = mockApi({
      "GET /student/diary": (init) => ({
        body: {
          week_start: new URL(init.url).searchParams.get("week"),
          today: "2026-11-16",
          lessons: [],
        },
      }),
    });
    renderRoutes(
      [{ path: "/student/diary", element: <DiaryPage /> }],
      "/student/diary?week=2026-11-16",
    );
    const spread = (await screen.findByRole("region", { name: "пн, 16 ноября" })).parentElement!
      .parentElement!;
    fireEvent.pointerDown(spread, { clientX: 300, pointerType: "touch" });
    fireEvent.pointerUp(spread, { clientX: 100, pointerType: "touch" });
    await waitFor(() => expect(calls.some((c) => c.path === "/student/diary")).toBe(true));
    expect(await screen.findByRole("region", { name: "пн, 23 ноября" })).toBeInTheDocument();
  });
});

describe("GradesPage", () => {
  it("shows subjects × dates and the details of a grade", async () => {
    mockApi({
      "GET /student/grades": {
        body: {
          period_from: "2026-11-01", period_to: "2026-12-31", period: "t2",
          terms: [{ id: "t2", name: "Модуль 2", starts_on: "2026-11-01", ends_on: "2026-12-31" }],
          scale: "100", low_below: "50.00",
          courses: [{
            course: "c1", subject_name: "Математика", group_name: "11-М", teacher_name: "Юсупов Т.",
            average: "65.00", low: false,
            grades: [{
              id: "g1", date: "2026-11-16", course: "c1", subject_name: "Математика", subject_short: "Мат",
              group_name: "11-М", topic: "Логарифмы", lesson_type_short: "Пр", value: 40,
              work_type_name: "Контрольная работа", weight: "2.00", comment: "разобрать ошибки",
              given_at: "2026-11-16T10:00:00Z", low: true,
            }],
          }],
          reviews: [{ subject_name: "Математика", teacher_name: "Юсупов Тимур", term_name: "Модуль 2",
            text: "Сильная алгебра, нужна геометрия.", updated_at: "2026-11-16T10:00:00Z" }],
        },
      },
    }); // prettier-ignore
    renderRoutes([{ path: "/student/grades", element: <GradesPage /> }], "/student/grades");
    expect(await screen.findByText("65.00")).toBeInTheDocument();
    const grade = screen.getByRole("button", { name: /^40, Математика/ });
    expect(grade).toHaveClass("low");
    await userEvent.click(grade);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Контрольная работа");
    expect(dialog).toHaveTextContent("×2");
    expect(dialog).toHaveTextContent("разобрать ошибки");
    expect(screen.queryByText(/место в группе/i)).not.toBeInTheDocument();
    expect(screen.getByText("Сильная алгебра, нужна геометрия.")).toBeInTheDocument();
  });
});

describe("AttendancePage", () => {
  it("shows per subject, overall, excused separately and the calendar", async () => {
    mockApi({
      "GET /student/attendance": {
        body: {
          period_from: "2026-09-01", period_to: "2026-11-16", threshold: 80, overall: "66.67", excused: 1,
          courses: [{ course: "c1", subject_name: "Математика", group_name: "11-М", percent: "66.67",
                      present: 1, late: 1, absent: 1, excused: 0, eligible: 3 }],
          month: "2026-11",
          days: [
            { date: "2026-11-01", lessons: 0, marks: [] },
            { date: "2026-11-02", lessons: 1, marks: [{ subject_short: "Мат", subject_name: "Математика", status: "absent" }] },
          ],
        },
      },
    }); // prettier-ignore
    renderRoutes(
      [{ path: "/student/attendance", element: <AttendancePage /> }],
      "/student/attendance",
    );
    const overall = await screen.findByRole("row", { name: /В целом/ });
    expect(within(overall).getByText("67%")).toHaveClass("low");
    expect(screen.getByText(/уважительной причине: 1/)).toBeInTheDocument();
    expect(screen.getByText("н Мат")).toBeInTheDocument();
  });
});

describe("student navigation", () => {
  it("has the five items of the bottom bar", async () => {
    mockApi({
      "GET /me": { body: { ...ME_STUDENT, groups: [{ id: "g", name: "11-М" }] } },
      "GET /auth/login": { body: BRANDING },
    });
    renderRoutes(
      [
        {
          path: "/student",
          element: <Gate section="student" />,
          children: [{ index: true, element: <p>home</p> }],
        },
      ],
      "/student",
    );
    await screen.findByText("home");
    const bars = screen.getAllByRole("navigation", { name: "Разделы" });
    const bottom = bars[bars.length - 1]!;
    expect(within(bottom).getAllByRole("link").map((a) => a.textContent)).toEqual([
      "Главная", "Дневник", "Оценки", "Тесты", "Расписание",
    ]); // prettier-ignore
  });
});
