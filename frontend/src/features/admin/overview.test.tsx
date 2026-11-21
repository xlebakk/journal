import { screen, within } from "@testing-library/react";

import { mockApi } from "@/test/api-mock";
import { renderRoutes } from "@/test/render";

import { OverviewPage } from "./OverviewPage";

const OVERVIEW = {
  today: "2026-11-23",
  lessons: { total: 4, conducted: 2, to_fill: 1, cancelled: 0 },
  unfilled: [],
  low_attendance: [],
  attendance_threshold: 80,
  attendance_window_days: 30,
  blocked_logins: [],
  failed_logins_24h: 0,
  denied: [
    { user: "u1", full_name: "Алиев Фарход", count: 25, last_hour: 14, spike: true,
      last_at: "2026-11-23T10:00:00Z" },
    { user: "u2", full_name: "Ганиева Мадина", count: 1, last_hour: 0, spike: false,
      last_at: "2026-11-23T06:00:00Z" },
  ],
  admin_new_devices: [
    { user: "a1", full_name: "Каримова Дилноза", at: "2026-11-22T19:00:00Z", ip: "10.1.2.3",
      user_agent: "Mozilla/5.0 (Linux; Android 15) Chrome/140.0" },
  ],
  audit: [],
}; // prettier-ignore

describe("OverviewPage, stage 7 blocks", () => {
  it("marks a spike of refusals and lists admin logins from new devices", async () => {
    mockApi({ "GET /admin/overview": { body: OVERVIEW } });
    renderRoutes([{ path: "/", element: <OverviewPage /> }], "/");
    const denied = await screen.findByRole("region", { name: "Отказы в доступе за сутки" });
    const rows = within(denied).getAllByRole("row");
    expect(within(rows[0]!).getByText(/всплеск/)).toHaveClass("error");
    expect(within(rows[0]!).getByText("25 за сутки, 14 за час")).toBeInTheDocument();
    expect(within(rows[1]!).queryByText(/всплеск/)).not.toBeInTheDocument();
    const devices = screen.getByRole("region", {
      name: "Входы администраторов с новых устройств за неделю",
    });
    expect(within(devices).getByText(/Chrome · Android/)).toBeInTheDocument();
    expect(within(devices).getByRole("link", { name: "сеансы" })).toHaveAttribute(
      "href",
      "/admin/users/a1",
    );
  });
});
