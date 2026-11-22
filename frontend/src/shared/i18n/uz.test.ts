import { formatHumanDate, formatJournalHeader } from "@/shared/lib/time";
import { formatDayLong, formatMonth, formatWeekRange, weekdayNames } from "@/shared/lib/week";

import { initLanguage, language, t } from ".";

// Its own file: the language is module state, and vitest isolates modules per file.
describe("Uzbek", () => {
  beforeAll(async () => {
    localStorage.setItem("journal.language", "uz");
    await initLanguage();
  });
  afterAll(() => localStorage.removeItem("journal.language"));

  it("switches the dictionary and <html lang>", () => {
    expect(language()).toBe("uz");
    expect(document.documentElement.lang).toBe("uz");
    expect(t("login.submit")).toBe("kirish");
  });

  it("writes dates without relying on Intl data for Uzbek", () => {
    expect(formatDayLong("2026-11-16")).toBe("du, 16-noyabr");
    expect(formatMonth("2026-11")).toBe("noyabr 2026");
    expect(formatWeekRange("2026-11-30")).toBe("30-noyabr – 6-dekabr 2026");
    expect(weekdayNames()[0]).toBe("dushanba");
    const evening = new Date("2026-11-20T19:30:00Z"); // already Saturday in Tashkent
    expect(formatJournalHeader(evening)).toBe("21.11.2026 · shanba");
    expect(formatHumanDate(evening)).toBe("sh, 21-noyabr");
  });
});
