import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BRANDING, ME_STUDENT, mockApi } from "@/test/api-mock";
import { renderRoutes } from "@/test/render";

import { Gate } from "./Gate";

const routes = [
  { path: "/login", element: <p>login page</p> },
  {
    element: <Gate mode="password" />,
    children: [{ path: "/change-password", element: <p>change password</p> }],
  },
  {
    element: <Gate mode="totp" />,
    children: [{ path: "/setup-2fa", element: <p>setup 2fa</p> }],
  },
  {
    path: "/admin",
    element: <Gate section="admin" />,
    children: [{ index: true, element: <p>admin area</p> }],
  },
  {
    path: "/student",
    element: <Gate section="student" />,
    children: [{ index: true, element: <p>student area</p> }],
  },
];

describe("Gate", () => {
  it("sends anonymous users to the login page", async () => {
    mockApi({ "GET /me": { status: 401 } });
    renderRoutes(routes, "/student");
    expect(await screen.findByText("login page")).toBeInTheDocument();
  });

  it("forces the temporary password change before anything else", async () => {
    mockApi({ "GET /me": { body: { ...ME_STUDENT, must_change_password: true } } });
    renderRoutes(routes, "/student");
    expect(await screen.findByText("change password")).toBeInTheDocument();
  });

  it("forces 2FA setup for administrators", async () => {
    mockApi({
      "GET /me": {
        body: { ...ME_STUDENT, roles: ["admin"], active_role: "admin", totp_setup_required: true },
      },
    });
    renderRoutes(routes, "/admin");
    // The lazy shell loads under a parallel run too.
    expect(await screen.findByText("setup 2fa", undefined, { timeout: 5000 })).toBeInTheDocument();
  });

  it("shows 404 for another role's section", async () => {
    mockApi({ "GET /me": { body: ME_STUDENT }, "GET /auth/login": { body: BRANDING } });
    renderRoutes(routes, "/admin");
    expect(await screen.findByText("Страница не найдена")).toBeInTheDocument();
    expect(screen.queryByText("admin area")).not.toBeInTheDocument();
  });

  it("renders the shell with the initials stamp and a keyboard menu", async () => {
    mockApi({ "GET /me": { body: ME_STUDENT }, "GET /auth/login": { body: BRANDING } });
    renderRoutes(routes, "/student");
    expect(await screen.findByText("student area")).toBeInTheDocument();
    const stamp = screen.getByRole("button", { name: "Меню пользователя Фарход Алиев" });
    expect(stamp).toHaveTextContent("ФА");

    const user = userEvent.setup();
    stamp.focus();
    await user.keyboard("{Enter}");
    const menu = await screen.findByRole("menu");
    for (const name of ["Профиль", "Сменить пароль", "Активные сеансы", "Выйти"]) {
      expect(screen.getByRole("menuitem", { name })).toBeInTheDocument();
    }
    expect(menu).toHaveTextContent("Алиев Фарход");
    expect(menu).toHaveTextContent("ученик");
    // A student has a single role: no role switcher.
    expect(screen.queryByText(/Перейти в роль/)).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
  });
});
