import { expect, test } from "@playwright/test";

import { login, logout, totp } from "./helpers";

// Must match seed_e2e.E2E_TOTP_SECRET_2.
const ADMIN2_SECRET = "KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU";

test("teacher sees the lesson, admin cancels it, the student sees «отменено»", async ({ page }) => {
  await login(page, "e2e.teacher");
  await page.getByRole("link", { name: "Расписание" }).click();
  await expect(page).toHaveURL(/\/teacher\/schedule$/);
  await expect(page.getByRole("button", { name: /Математика/ })).toBeVisible();
  await logout(page);

  await login(page, "e2e.admin2");
  await page.getByLabel("Код").fill(totp(ADMIN2_SECRET));
  await page.getByRole("button", { name: "подтвердить" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByRole("link", { name: "Расписание" }).first().click();
  await page.getByRole("button", { name: /Математика/ }).click();
  const dialog = page.getByRole("dialog");
  // Stage 19: the card shows the lesson first, then «изменить» / «удалить занятие».
  await dialog.getByRole("button", { name: "удалить занятие" }).click();
  await dialog.getByLabel("Причина").fill("Преподаватель на олимпиаде");
  await dialog.getByRole("button", { name: "удалить занятие" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText("отменено")).toBeVisible();
  await logout(page);

  await login(page, "e2e.student");
  await page.getByRole("link", { name: "Расписание" }).click();
  await expect(page).toHaveURL(/\/student\/schedule$/);
  await expect(page.getByText("Математика").first()).toBeVisible();
  await expect(page.getByText("отменено").first()).toBeVisible();
  // The student cannot reach staff schedule endpoints.
  expect((await page.request.get("/api/v1/admin/lessons")).status()).toBe(403);
  expect((await page.request.get("/api/v1/teacher/schedule")).status()).toBe(403);
});
