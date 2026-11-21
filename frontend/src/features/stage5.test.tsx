import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { actionText, changes } from "@/features/admin/audit/labels";
import { ImportPage } from "@/features/admin/import/ImportPage";
import { ExamPage } from "@/features/exams/ExamPage";
import { TestsPage } from "@/features/student/TestsPage";
import { ME_STUDENT, mockApi } from "@/test/api-mock";
import { renderRoutes } from "@/test/render";
import { LinkifiedText } from "@/shared/ui";

const ME_TEACHER = { ...ME_STUDENT, roles: ["teacher"], active_role: "teacher" };

describe("TestsPage", () => {
  it("shows results in % with the goal line, the change and an absence", async () => {
    mockApi({
      "GET /student/exams": {
        body: [
          {
            subject: "s1",
            subject_name: "Математика",
            target_percent: 80,
            exams: [
              { exam: "e1", title: "Пробный № 1", date: "2026-10-05", total: 18, max_score: 30,
                percent: "60.0", change: null, was_absent: false, sections: [] },
              { exam: "e2", title: "Пробный № 2", date: "2026-10-26", total: null, max_score: 30,
                percent: null, change: null, was_absent: true, sections: [] },
              { exam: "e3", title: "Пробный № 3", date: "2026-11-16", total: 84, max_score: 100,
                percent: "84.0", change: "24.0", was_absent: false,
                sections: [{ name: "Алгебра", score: 50, max_score: 60, percent: "83.3" }] },
            ],
          },
        ],
      }, // prettier-ignore
    });
    renderRoutes([{ path: "/", element: <TestsPage /> }], "/");
    const chart = await screen.findByRole("img", { name: /Математика/ });
    expect(within(chart).getByText("Цель: 80%")).toBeInTheDocument();
    expect(within(chart).getByText("18 / 30")).toBeInTheDocument();
    const rows = screen.getAllByRole("row");
    expect(within(rows[1]!).getByText("60%")).toHaveClass("low");
    expect(within(rows[2]!).getByText("не был")).toBeInTheDocument();
    expect(within(rows[3]!).getByText("+24")).toBeInTheDocument();
    expect(within(rows[3]!).getByText(/Алгебра 50\/60/)).toBeInTheDocument();
  });
});

describe("LinkifiedText", () => {
  it("links only https addresses and never parses HTML", () => {
    render(
      <p>
        <LinkifiedText text="См. https://example.com/a, а не javascript:alert(1) и <b>жирный</b>" />
      </p>,
    );
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://example.com/a");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText(/<b>жирный<\/b>/)).toBeInTheDocument();
    expect(document.querySelector("b")).toBeNull();
  });
});

describe("audit labels", () => {
  it("translates actions and lists changed fields only", () => {
    expect(actionText("journal.grade_create")).toBe("журнал: оценка");
    expect(actionText("something.odd")).toBe("something.odd");
    expect(changes({ a: 1, b: "x" }, { a: 2, b: "x", c: null })).toEqual([
      { field: "a", before: "1", after: "2" },
      { field: "c", before: "", after: "—" },
    ]);
  });
});

const EXAM = {
  id: "e1", title: "Пробный ДТМ", subject: "s1", subject_name: "Математика", date: "2026-11-14",
  max_score: 30, courses: [{ id: "c1", group_name: "11-М", teacher_name: "Юсупов Т." }],
  sections: [], results_count: 0, version: 1,
}; // prettier-ignore
const ROW = {
  student: "u1", student_name: "Алиев Фарход", login: "aliev.f", group_name: "11-М",
  result: null, total: null, percent: null, was_absent: false, comment: "", sections: {},
  version: null,
}; // prettier-ignore

describe("ExamPage", () => {
  it("saves a total on blur", async () => {
    const { calls } = mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /exams/e1/results": {
        body: { exam: EXAM, editable: true, needs_reason: false, locked: null,
                window_closes_on: "2026-11-21", rows: [ROW] }, // prettier-ignore
      },
      "PUT /exams/e1/results/u1": {
        body: { ...ROW, result: "r1", total: 24, percent: "80.0", version: 1 },
      },
    });
    renderRoutes([{ path: "/teacher/exams/:id", element: <ExamPage /> }], "/teacher/exams/e1");
    const input = await screen.findByRole("textbox", { name: "Алиев Фарход: Итог" });
    await userEvent.type(input, "24");
    await userEvent.tab();
    await waitFor(() => expect(screen.getByText("80%")).toBeInTheDocument());
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toMatchObject({ total: 24, was_absent: false, version: null });
  });

  it("locks the table after the edit window for a teacher", async () => {
    mockApi({
      "GET /me": { body: ME_TEACHER },
      "GET /exams/e1/results": {
        body: { exam: EXAM, editable: false, needs_reason: false, locked: "window",
                window_closes_on: "2026-11-21", rows: [ROW] }, // prettier-ignore
      },
    });
    renderRoutes([{ path: "/teacher/exams/:id", element: <ExamPage /> }], "/teacher/exams/e1");
    expect(await screen.findByText(/Изменить может администратор/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Алиев Фарход: Итог" })).toBeDisabled();
  });
});

describe("ImportPage", () => {
  const file = () => new File(["Фамилия;Имя\nАлиев;Фарход"], "s.csv", { type: "text/csv" });

  it("shows errors per line and offers no import until they are fixed", async () => {
    mockApi({
      "POST /admin/import/students": {
        body: {
          applied: false,
          created: [],
          rows: [
            { line: 2, last_name: "Алиев", first_name: "Фарход", middle_name: "", login: "",
              group_name: "", issues: [], warnings: [] },
            { line: 3, last_name: "", first_name: "Али", middle_name: "", login: "taken",
              group_name: "", issues: ["last_name:required", "login:login_taken"], warnings: [] },
          ],
        },
      }, // prettier-ignore
    });
    renderRoutes([{ path: "/", element: <ImportPage /> }], "/");
    await userEvent.upload(screen.getByLabelText("Файл XLSX или CSV"), file());
    await userEvent.click(screen.getByRole("button", { name: "проверить файл" }));
    expect(await screen.findByText(/Фамилия: Обязательное поле/)).toBeInTheDocument();
    expect(screen.getByText(/Логин: /)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "создать учеников" })).not.toBeInTheDocument();
  });

  it("creates students and prints access cards with one-time passwords", async () => {
    let applied = false;
    mockApi({
      "POST /admin/import/students": () => {
        const body = applied
          ? {
              applied: true,
              rows: [],
              created: [{ id: "u1", full_name: "Алиев Фарход", login: "aliev.f",
                          temporary_password: "hK7mPq2xRt9z", group_name: "11-М" }],
            } // prettier-ignore
          : {
              applied: false,
              created: [],
              rows: [{ line: 2, last_name: "Алиев", first_name: "Фарход", middle_name: "",
                       login: "", group_name: "11-М", issues: [], warnings: [] }],
            }; // prettier-ignore
        applied = true;
        return { body };
      },
      "GET /admin/access-cards": {
        body: { center_name: "Центр", site_url: "https://journal.example.com", qr: "data:image/svg+xml;base64,AA==" },
      }, // prettier-ignore
    });
    renderRoutes([{ path: "/", element: <ImportPage /> }], "/");
    await userEvent.upload(screen.getByLabelText("Файл XLSX или CSV"), file());
    await userEvent.click(screen.getByRole("button", { name: "проверить файл" }));
    await userEvent.click(await screen.findByRole("button", { name: "создать учеников" }));
    expect(await screen.findByText("hK7mPq2xRt9z")).toBeInTheDocument();
    expect(await screen.findByText("https://journal.example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "печать карточек" })).toBeInTheDocument();
  });
});
