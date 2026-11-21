import { formatDate, formatHumanDate, formatJournalHeader, formatTime } from "./time";

describe("center time zone (Asia/Tashkent, UTC+5)", () => {
  // 19:30 UTC on Thursday 19 Nov is already 00:30 on Friday 20 Nov in Tashkent.
  const lateEveningUtc = new Date("2026-11-19T19:30:00Z");

  it("rolls the date over at the center's midnight, not UTC's", () => {
    expect(formatDate(lateEveningUtc)).toBe("20.11.2026");
    expect(formatTime(lateEveningUtc)).toBe("00:30");
  });

  it("formats the journal header and human dates", () => {
    expect(formatJournalHeader(lateEveningUtc)).toBe("20.11.2026 · пятница");
    expect(formatHumanDate(lateEveningUtc)).toBe("пт, 20 ноября");
  });

  it("uses 24-hour time", () => {
    expect(formatTime(new Date("2026-11-21T09:05:00Z"))).toBe("14:05");
  });
});
