import {
  addDays,
  centerToday,
  formatDayLong,
  formatDayShort,
  formatWeekRange,
  hhmm,
  isoWeekday,
  startOfWeek,
  weekDays,
} from "./week";

describe("week helpers", () => {
  it("uses the center's date, not the browser's or UTC", () => {
    // 20:30 UTC on Sunday 15 Nov is already Monday 16 Nov in Tashkent.
    expect(centerToday(new Date("2026-11-15T20:30:00Z"))).toBe("2026-11-16");
    expect(centerToday(new Date("2026-11-15T18:59:00Z"))).toBe("2026-11-15");
  });

  it("starts weeks on Monday", () => {
    expect(isoWeekday("2026-11-16")).toBe(1);
    expect(isoWeekday("2026-11-22")).toBe(7);
    expect(startOfWeek("2026-11-22")).toBe("2026-11-16");
    expect(weekDays("2026-11-16")).toHaveLength(7);
    expect(addDays("2026-11-30", 1)).toBe("2026-12-01");
  });

  it("formats dates the human way", () => {
    expect(formatDayLong("2026-11-20")).toBe("пт, 20 ноября");
    expect(formatDayShort("2026-11-16")).toBe("пн 16.11");
    expect(formatWeekRange("2026-11-16")).toBe("16–22 ноября 2026 г.");
    expect(formatWeekRange("2026-11-30")).toBe("30 ноября – 6 декабря 2026 г.");
    expect(hhmm("14:00:00")).toBe("14:00");
  });
});
