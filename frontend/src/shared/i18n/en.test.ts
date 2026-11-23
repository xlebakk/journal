import { formatDayLong, formatWeekRange } from "@/shared/lib/week";

import { initLanguage, language, t } from ".";

// Its own file: the language is module state, and vitest isolates modules per file.
describe("English", () => {
  beforeAll(async () => {
    localStorage.setItem("journal.language", "en");
    await initLanguage();
  });
  afterAll(() => localStorage.removeItem("journal.language"));

  it("switches the dictionary, <html lang> and dates", () => {
    expect(language()).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    expect(t("login.signIn")).toBe("Sign in to the journal");
    expect(formatDayLong("2026-11-16")).toBe("Mon, 16 November");
    expect(formatWeekRange("2026-11-16")).toBe("16–22 November 2026");
  });
});
