import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockApi } from "@/test/api-mock";
import { withQuery } from "@/test/render";

import { CalendarSection } from "./CalendarSection";

const LINK = "https://journal.example.uz/api/v1/calendar/f1.ics?token=abc";
const NONE = { url: null, created_at: null, last_used_at: null };
const ISSUED = { url: LINK, created_at: "2026-11-16T05:00:00Z", last_used_at: null };

describe("CalendarSection", () => {
  it("creates, reissues after a confirmation and revokes the link", async () => {
    const { calls } = mockApi({
      "GET /me/calendar": { body: NONE },
      "POST /me/calendar": { status: 201, body: ISSUED },
      "DELETE /me/calendar": { status: 204 },
    });
    withQuery(<CalendarSection activeRole="student" />);
    await userEvent.click(await screen.findByRole("button", { name: "Создать ссылку" }));
    expect(await screen.findByLabelText("Ссылка для подписки")).toHaveValue(LINK);
    expect(screen.getByText(/Создана 16\.11\.2026, 10:00/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть в календаре" })).toHaveAttribute(
      "href",
      LINK.replace("https:", "webcal:"),
    );

    await userEvent.click(screen.getByRole("button", { name: "Перевыпустить" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Старая ссылка сразу перестанет работать");
    await userEvent.click(within(dialog).getByRole("button", { name: "Перевыпустить" }));
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(2);

    await userEvent.click(screen.getByRole("button", { name: "Отключить" }));
    expect(await screen.findByRole("button", { name: "Создать ссылку" })).toBeInTheDocument();
    expect(calls.at(-1)?.method).toBe("DELETE");
  });
});
