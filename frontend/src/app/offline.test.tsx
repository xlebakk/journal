import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { shouldShowIosInstallHint } from "@/shared/lib/userAgent";
import { renderRoutes } from "@/test/render";

import { Gate } from "./Gate";

describe("offline", () => {
  it("shows «Нет соединения» instead of a broken page and retries", async () => {
    let online = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        if (!online) throw new TypeError("Failed to fetch");
        return new Response("{}", { status: 401, headers: { "Content-Type": "application/json" } });
      }),
    );
    renderRoutes(
      [
        { path: "/student", element: <Gate section="student" /> },
        { path: "/login", element: <p>вход</p> },
      ],
      "/student",
    );
    expect(await screen.findByRole("heading", { name: "Нет соединения" })).toBeInTheDocument();
    online = true;
    await userEvent.click(screen.getByRole("button", { name: "повторить" }));
    expect(await screen.findByText("вход")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});

describe("iPhone install hint", () => {
  const nav = (userAgent: string, extra: object = {}) =>
    ({ userAgent, platform: "iPhone", maxTouchPoints: 5, ...extra }) as Navigator & {
      standalone?: boolean;
    };

  it("appears in Safari on iPhone until the journal is on the home screen", () => {
    const safari = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1";
    expect(shouldShowIosInstallHint(nav(safari), false)).toBe(true);
    expect(shouldShowIosInstallHint(nav(safari, { standalone: true }), false)).toBe(false);
    expect(shouldShowIosInstallHint(nav(safari), true)).toBe(false);
    const android = "Mozilla/5.0 (Linux; Android 15) Chrome/140.0";
    expect(shouldShowIosInstallHint(nav(android, { platform: "Linux" }), false)).toBe(false);
  });
});
