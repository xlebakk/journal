import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { GradesPage } from "@/features/student/GradesPage";
import { api } from "@/shared/api/client";
import { mockApi } from "@/test/api-mock";
import { renderRoutes } from "@/test/render";

import { ChildSwitcher } from "./ChildSwitcher";

const CHILDREN = [
  { id: "c1", full_name: "Алиев Фарход", short_name: "Алиев Ф.", groups: ["11-М"] },
  { id: "c2", full_name: "Алиева Мадина", short_name: "Алиева М.", groups: ["10-М"] },
];
const NO_GRADES = {
  period_from: "2026-11-01", period_to: "2026-12-31", period: "t2", terms: [], scale: "100",
  low_below: "50.00", courses: [], reviews: [],
}; // prettier-ignore

describe("a parent looks at a child (stage 14)", () => {
  afterEach(() => sessionStorage.clear());

  it("sends the chosen child with every student page request, and only there", async () => {
    const { calls } = mockApi({
      "GET /parent/children": { body: CHILDREN },
      "GET /student/grades": { body: NO_GRADES },
      "GET /announcements": { body: [] },
    });
    renderRoutes(
      [
        {
          path: "/student/grades",
          element: (
            <>
              <ChildSwitcher />
              <GradesPage />
            </>
          ),
        },
      ],
      "/student/grades",
    );
    const select = await screen.findByLabelText("Ребёнок");
    expect(select).toHaveValue("c1"); // the server's default: the first child
    await userEvent.selectOptions(select, "c2");
    await waitFor(() =>
      expect(calls.some((c) => c.path === "/student/grades" && c.url?.includes("child=c2"))).toBe(
        true,
      ),
    );
    expect(sessionStorage.getItem("journal.child")).toBe("c2");
    await api("/announcements");
    expect(calls.at(-1)?.url).not.toContain("child=");
  });

  it("shows the name of a single child instead of a select", async () => {
    mockApi({ "GET /parent/children": { body: [CHILDREN[0]] } });
    renderRoutes([{ path: "/", element: <ChildSwitcher /> }], "/");
    expect(await screen.findByText("Алиев Фарход")).toBeInTheDocument();
    expect(screen.queryByLabelText("Ребёнок")).not.toBeInTheDocument();
  });
});
