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
  await page.getByRole("link", { name: "Алиев Фарход" }).click();
  const parents = page.getByRole("region", { name: "Родители" });
  await parents.getByLabel("Фамилия").fill("Алиева");
  await parents.getByLabel("Имя").fill("Гульнора");
  await parents.getByRole("button", { name: "добавить родителя" }).click();

  const dialog = page.getByRole("dialog", { name: "Временный пароль" });
  const values = dialog.locator("dd");
  const parentLogin = (await values.nth(0).textContent())!.trim();
  const temporary = (await values.nth(1).textContent())!.trim();
  await dialog.getByRole("button", { name: "готово" }).click();
  await expect(parents.getByRole("link", { name: "Алиева Гульнора" })).toBeVisible();
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
