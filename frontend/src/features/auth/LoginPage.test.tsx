import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BRANDING, ME_STUDENT, mockApi } from "@/test/api-mock";
import { renderRoutes } from "@/test/render";

import { LoginPage } from "./LoginPage";

const routes = [
  { path: "/login", Component: LoginPage },
  { path: "/", element: <p>home</p> },
];

async function fillAndSubmit(login = "aliev.f", password = "secret-password") {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Логин"), login);
  await user.type(screen.getByLabelText("Пароль"), password);
  await user.click(screen.getByRole("button", { name: "войти" }));
  return user;
}

describe("LoginPage", () => {
  it("shows the journal header, center name and help line without a sign-up link", async () => {
    mockApi({ "GET /me": { status: 401 }, "GET /auth/login": { body: BRANDING } });
    renderRoutes(routes, "/login");
    expect(await screen.findByRole("heading", { name: BRANDING.center_name })).toBeInTheDocument();
    expect(screen.getByText(/^\d{2}\.\d{2}\.\d{4} · /)).toBeInTheDocument();
    expect(screen.getByText(/Обратитесь к администратору центра: \+998 71/)).toBeInTheDocument();
    expect(screen.queryByText(/регистр/i)).not.toBeInTheDocument();
  });

  it("shows one message for any wrong credentials and clears the password", async () => {
    mockApi({
      "GET /me": { status: 401 },
      "GET /auth/login": { body: BRANDING },
      "POST /auth/login": { status: 400, body: { detail: "invalid_credentials" } },
    });
    renderRoutes(routes, "/login");
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent("Неверный логин или пароль");
    expect(screen.getByLabelText("Пароль")).toHaveValue("");
  });

  it("shows the lockout time", async () => {
    mockApi({
      "GET /me": { status: 401 },
      "GET /auth/login": { body: BRANDING },
      "POST /auth/login": {
        status: 429,
        body: { detail: "too_many_attempts", retry_after_minutes: 15 },
      },
    });
    renderRoutes(routes, "/login");
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Слишком много попыток. Попробуйте через 15 мин.",
    );
  });

  it("asks for the TOTP code, then goes home", async () => {
    let loggedIn = false;
    const { calls } = mockApi({
      "GET /me": () => (loggedIn ? { body: ME_STUDENT } : { status: 401 }),
      "GET /auth/login": { body: BRANDING },
      "POST /auth/login": { body: { step: "totp" } },
      "POST /auth/totp": () => {
        loggedIn = true;
        return { body: { step: "done" } };
      },
    });
    const { router } = renderRoutes(routes, "/login");
    const user = await fillAndSubmit();
    await user.type(await screen.findByLabelText("Код"), "123456");
    await user.click(screen.getByRole("button", { name: "подтвердить" }));
    await waitFor(() => expect(router.state.location.pathname).not.toBe("/login"));
    expect(calls.find((c) => c.path === "/auth/totp")?.body).toEqual({ code: "123456" });
  });

  it("sends the CSRF token from the cookie", async () => {
    // jsdom refuses __Host- cookies on http:// (Chrome/Firefox accept them on localhost).
    vi.spyOn(document, "cookie", "get").mockReturnValue("other=1; __Host-csrftoken=tok123");
    const { fetchMock } = mockApi({
      "GET /me": { status: 401 },
      "GET /auth/login": { body: BRANDING },
      "POST /auth/login": { status: 400, body: { detail: "invalid_credentials" } },
    });
    renderRoutes(routes, "/login");
    await fillAndSubmit();
    await screen.findByRole("alert");
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect((post?.[1]?.headers as Record<string, string>)["X-CSRFToken"]).toBe("tok123");
  });
});
