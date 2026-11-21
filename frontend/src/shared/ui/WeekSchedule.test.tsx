import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ScheduleIssues } from "./ScheduleIssues";
import type { ScheduleItem } from "./scheduleMarks";
import { WeekSchedule } from "./WeekSchedule";

const base: ScheduleItem = {
  id: "1",
  date: "2026-11-16",
  start_time: "16:00:00",
  end_time: "17:30:00",
  subject_name: "Математика",
  subject_short: "Мат",
  group_name: "11-М вечерняя",
  teacher_name: "Юсупов Т.",
  room_name: "101",
  lesson_type_short: "Пр",
  status: "planned",
  cancel_reason: "",
  is_extra: false,
  is_moved: false,
  is_room_changed: false,
  is_substituted: false,
  planned_date: "2026-11-16",
  planned_start_time: "16:00:00",
  planned_room_name: "101",
};

describe("WeekSchedule", () => {
  it("puts lessons into a timetable by start time and day", () => {
    render(
      <WeekSchedule
        monday="2026-11-16"
        today="2026-11-18"
        lessons={[base, { ...base, id: "2", date: "2026-11-18", subject_name: "Физика" }]}
        showGroup
      />,
    );
    const table = screen.getByRole("table");
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers.slice(1)).toEqual([
      "пн 16.11",
      "вт 17.11",
      "ср 18.11",
      "чт 19.11",
      "пт 20.11",
      "сб 21.11",
    ]);
    expect(within(table).getByRole("rowheader", { name: "16:00" })).toBeInTheDocument();
    expect(screen.getByText("Физика")).toBeInTheDocument();
    // Sunday is hidden when nothing happens on it.
    expect(headers).not.toContain("вс 22.11");
  });

  it("marks changes in words, not only colour", () => {
    render(
      <WeekSchedule
        monday="2026-11-16"
        today="2026-11-16"
        lessons={[
          { ...base, status: "cancelled", cancel_reason: "болезнь" },
          {
            ...base,
            id: "2",
            date: "2026-11-21",
            start_time: "14:00:00",
            is_moved: true,
            planned_date: "2026-11-19",
            planned_start_time: "16:00:00",
          },
          { ...base, id: "3", date: "2026-11-17", is_substituted: true, teacher_name: "Ким С." },
        ]}
      />,
    );
    expect(screen.getByText("отменено")).toBeInTheDocument();
    expect(screen.getByText("перенесено с чт, 19 ноября 16:00")).toBeInTheDocument();
    expect(screen.getByText("замена: Ким С.")).toBeInTheDocument();
  });

  it("makes lessons clickable only when a handler is given", async () => {
    const onSelect = vi.fn();
    const { rerender } = render(
      <WeekSchedule monday="2026-11-16" today="2026-11-16" lessons={[base]} />,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    rerender(
      <WeekSchedule monday="2026-11-16" today="2026-11-16" lessons={[base]} onSelect={onSelect} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Математика/ }));
    expect(onSelect).toHaveBeenCalledWith(base);
  });

  it("says so when the week is empty", () => {
    render(<WeekSchedule monday="2026-11-16" today="2026-11-16" lessons={[]} />);
    expect(screen.getByText("На этой неделе занятий нет.")).toBeInTheDocument();
  });
});

describe("ScheduleIssues", () => {
  it("explains conflicts and warnings", () => {
    render(
      <ScheduleIssues
        conflicts={[
          {
            kind: "teacher",
            date: "2026-11-16",
            start_time: "16:00",
            end_time: "17:30",
            group: "11-Г",
            subject: "Физика",
            teacher: "Ким С.",
            room: "102",
          },
        ]}
        warnings={[
          { kind: "capacity", date: "2026-11-16", room: "202", capacity: 12, students: 15 },
        ]}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "преподаватель занят: пн, 16 ноября 16:00–17:30",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "в кабинете 202 12 мест, в группе 15 учеников",
    );
  });
});
