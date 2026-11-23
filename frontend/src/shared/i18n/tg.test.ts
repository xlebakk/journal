import { formatHumanDate, formatJournalHeader } from "@/shared/lib/time";
import { formatDayLong, formatMonth, formatWeekRange, weekdayNames } from "@/shared/lib/week";

import { initLanguage, language, t } from ".";

// Its own file: the language is module state, and vitest isolates modules per file.
describe("Tajik", () => {
  beforeAll(async () => {
    localStorage.setItem("journal.language", "tg");
    await initLanguage();
  });
  afterAll(() => localStorage.removeItem("journal.language"));

  it("switches the dictionary and <html lang>", () => {
    expect(language()).toBe("tg");
    expect(document.documentElement.lang).toBe("tg");
    expect(t("login.submit")).toBe("Ворид шудан");
  });

  it("writes dates from the dictionary, not from Intl", () => {
    expect(formatDayLong("2026-11-16")).toBe("дш, 16 ноябр");
    expect(formatMonth("2026-11")).toBe("ноябр 2026");
    expect(formatWeekRange("2026-11-30")).toBe("30 ноябр – 6 декабр 2026");
    expect(weekdayNames()[0]).toBe("душанбе");
    const evening = new Date("2026-11-20T19:30:00Z"); // already Saturday in the center
    expect(formatJournalHeader(evening)).toBe("21.11.2026 · шанбе");
    expect(formatHumanDate(evening)).toBe("шб, 21 ноябр");
  });
});
