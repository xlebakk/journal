import { expect, test } from "@playwright/test";

import { login, logout, totp } from "./helpers";

const ADMIN5_SECRET = "OBQXEZLOORZWC3DPNZSWY6LMNFZXIZLO";

test("admin adds a parent from the student's card; the parent reads the child's pages", async ({
  page,
}) => {
  await login(page, "e2e.admin5");
  await page.getByLabel("Код").fill(totp(ADMIN5_SECRET));
  await page.getByRole("button", { name: "подтвердить" }).click();
  await expect(page).toHaveURL(/\/admin$/);

  await page.getByRole("link", { name: "Пользователи" }).first().click();
  await page.getByLabel("Поиск по ФИО или логину").fill("e2e.student");
  // The list refreshes after the search: click once it shows only the student.
  await expect(page.getByText("Показано 1 из 1")).toBeVisible();
  await page.getByRole("link", { name: "Алиев Фарход" }).click();
  await expect(page.getByRole("heading", { name: "Алиев Фарход" })).toBeVisible();
  const parents = page.getByRole("region", { name: "Родители" });
  await parents.getByLabel("Фамилия").fill("Алиева");
  await parents.getByLabel("Имя").fill("Гульнора");
  const temporary = "мамин пароль от центра";
  await parents.getByLabel("Пароль", { exact: true }).fill(temporary);
  await parents.getByLabel("Попросить сменить пароль при первом входе").check();
  await parents.getByRole("button", { name: "добавить родителя" }).click();
  await expect(parents.getByRole("link", { name: "Алиева Гульнора" })).toBeVisible();
  const parentLogin = (await parents
    .getByRole("row")
    .nth(1)
    .locator("td")
    .nth(1)
    .textContent())!.trim();
  await logout(page);

  await login(page, parentLogin, temporary);
  await page.getByLabel("Текущий пароль").fill(temporary);
  await page.getByLabel("Новый пароль", { exact: true }).fill("родительский пароль 2026");
  await page.getByLabel("Новый пароль ещё раз").fill("родительский пароль 2026");
  await page.getByRole("button", { name: "сменить пароль" }).click();
  await expect(page).toHaveURL(/\/student$/);
  await expect(page.getByRole("banner").getByText("Алиев Фарход")).toBeVisible();

  await page.getByRole("link", { name: "Оценки" }).first().click();
  await expect(page.getByRole("heading", { name: "Оценки" })).toBeVisible();
  // Read-only: the journal and the administration stay closed on the server.
  expect((await page.request.get("/api/v1/journal/courses")).status()).toBe(403);
  expect((await page.request.get("/api/v1/admin/users")).status()).toBe(403);
});
