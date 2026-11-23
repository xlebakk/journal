import { expect, test } from "@playwright/test";

import { PASSWORD } from "./helpers";

test("the interface switches to Tajik on the login page and stays so after login", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("radio", { name: "Тоҷикӣ" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "tg");
  await expect(page.getByText("Журнали электронӣ")).toBeVisible();

  await page.getByLabel("Логин").fill("e2e.student");
  await page.getByLabel("Рамз", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Ворид шудан" }).click();
  await expect(page).toHaveURL(/\/student$/);
  await expect(page.getByRole("heading", { name: "Баҳоҳои нав дар 7 рӯз" })).toBeVisible();

  // English from the profile, then back to Russian.
  await page.goto("/account/profile");
  await page.getByRole("radio", { name: "English" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { name: "Security" })).toBeVisible();
  await page.getByRole("radio", { name: "Русский" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.getByRole("heading", { name: "Безопасность" })).toBeVisible();
});
