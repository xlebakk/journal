import { expect, test } from "@playwright/test";

import { login, logout, totp } from "./helpers";

// Must match seed_e2e.E2E_TOTP_SECRET_3.
const ADMIN3_TOTP_SECRET = "MFRGGZDFMZTWQ2LKNNWG23TPOBYXE43U";

// No group: the journal scenario counts the members of the e2e group.
const CSV = [
  "Фамилия*;Имя*;Отчество;Логин;Группа;Класс",
  "Турсунова;Севара;;;;11",
  ";Без фамилии;;;;",
].join("\n");

test("admin imports students: errors per line, then one transaction and access cards", async ({
  page,
}) => {
  await login(page, "e2e.admin3");
  await page.getByLabel("Код").fill(totp(ADMIN3_TOTP_SECRET));
  await page.getByRole("button", { name: "подтвердить" }).click();
  await expect(page).toHaveURL(/\/admin$/);

  await page.getByRole("link", { name: "Импорт" }).click();
  await expect(page).toHaveURL(/\/admin\/import$/);
  const fileInput = page.getByLabel("Файл XLSX или CSV");

  // A file with an error: the preview names the line, nothing can be imported yet.
  await fileInput.setInputFiles({
    name: "students.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(CSV, "utf-8"),
  });
  await page.getByRole("button", { name: "проверить файл" }).click();
  await expect(page.getByText(/Фамилия: Обязательное поле/)).toBeVisible();
  await expect(page.getByRole("button", { name: "создать учеников" })).toHaveCount(0);

  // The fixed file passes and creates the student with a generated login.
  await fileInput.setInputFiles({
    name: "students.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(CSV.split("\n").slice(0, 2).join("\n"), "utf-8"),
  });
  await page.getByRole("button", { name: "проверить файл" }).click();
  await expect(page.getByText("без ошибок")).toBeVisible();
  await page.getByRole("button", { name: "создать учеников" }).click();

  const card = page.getByRole("article").filter({ hasText: "Турсунова Севара" });
  await expect(card).toBeVisible();
  await expect(card.getByText("tursunova.s")).toBeVisible();
  const password = (await card.locator("dd").nth(1).textContent())?.trim() ?? "";
  expect(password).toHaveLength(12);
  await expect(page.getByRole("button", { name: "печать карточек" })).toBeVisible();

  await logout(page);

  // The card works: the new student logs in and must change the temporary password.
  await login(page, "tursunova.s", password);
  await expect(page).toHaveURL(/\/change-password$/);
});
