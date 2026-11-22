import { expect, test } from "@playwright/test";

import { ADMIN_TOTP_SECRET, login, logout, PASSWORD, totp } from "./helpers";

test("student lands on the student home and cannot open the admin section", async ({ page }) => {
  await login(page, "e2e.student");
  await expect(page).toHaveURL(/\/student$/);
  await expect(page.getByRole("heading", { name: "Новые оценки за 7 дней" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Меню пользователя Фарход Алиев" })).toContainText(
    "ФА",
  );

  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: "Страница не найдена" })).toBeVisible();
  // The server refuses too, whatever the client shows.
  const api = await page.request.get("/api/v1/admin/users");
  expect(api.status()).toBe(403);
});

test("teacher lands on «Сегодня»", async ({ page }) => {
  await login(page, "E2E.Teacher "); // case and spaces do not matter
  await expect(page).toHaveURL(/\/teacher$/);
  await expect(page.getByRole("heading", { name: "Сегодня" })).toBeVisible();
  await logout(page);
  expect((await page.request.get("/api/v1/me")).status()).toBe(401);
});

test("wrong password shows the neutral message", async ({ page }) => {
  await login(page, "e2e.student", "not-the-password");
  await expect(page.getByRole("alert")).toHaveText("Неверный логин или пароль");
  await expect(page).toHaveURL(/\/login$/);
});

test("admin passes 2FA, creates a student; the student must change the temporary password", async ({
  page,
}) => {
  await login(page, "e2e.admin");
  await page.getByLabel("Код").fill(totp(ADMIN_TOTP_SECRET));
  await page.getByRole("button", { name: "подтвердить" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("heading", { name: "Обзор" })).toBeVisible();

  await page.getByRole("link", { name: "Пользователи" }).first().click();
  await page.getByRole("link", { name: "добавить пользователя" }).click();
  await page.getByLabel("Фамилия").fill("Рахимова");
  await page.getByLabel("Имя").fill("Севара");
  await page.getByLabel("ученик").check();
  // The administrator types the first password and asks to change it at the first login.
  const temporary = "пароль от администратора";
  await page.getByLabel("Пароль", { exact: true }).fill(temporary);
  await page.getByLabel("Попросить сменить пароль при первом входе").check();
  await page.getByRole("button", { name: "создать" }).click();

  await expect(page.getByRole("heading", { name: "Рахимова Севара" })).toBeVisible();
  const newLogin = "rakhimova.s";
  await expect(page.getByText(newLogin, { exact: true })).toBeVisible();
  await logout(page);

  await login(page, newLogin, temporary);
  await expect(page).toHaveURL(/\/change-password$/);
  await expect(page.getByText("Это временный пароль")).toBeVisible();
  // Nothing else is reachable until the password is changed.
  expect((await page.request.get("/api/v1/auth/sessions")).status()).toBe(403);

  await page.getByLabel("Текущий пароль").fill(temporary);
  await page.getByLabel("Новый пароль", { exact: true }).fill("тёплый ветер с гор 2026");
  await page.getByLabel("Новый пароль ещё раз").fill("тёплый ветер с гор 2026");
  await page.getByRole("button", { name: "сменить пароль" }).click();
  await expect(page).toHaveURL(/\/student$/);
});

test("seeded user with a temporary password is forced to change it", async ({ page }) => {
  await login(page, "e2e.new");
  await expect(page).toHaveURL(/\/change-password$/);
  await page.goto("/student");
  await expect(page).toHaveURL(/\/change-password$/);
  await page.getByLabel("Текущий пароль").fill(PASSWORD);
  await page.getByLabel("Новый пароль", { exact: true }).fill("short");
  await page.getByLabel("Новый пароль ещё раз").fill("short");
  await page.getByRole("button", { name: "сменить пароль" }).click();
  await expect(page.getByText("Не короче 10 символов").first()).toBeVisible();
});
