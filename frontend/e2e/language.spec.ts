import { expect, test } from "@playwright/test";

import { PASSWORD } from "./helpers";

test("the interface switches to Uzbek on the login page and stays so after login", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByRole("radio", { name: "Oʻzbekcha" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "uz");
  await expect(page.getByText("Elektron jurnal")).toBeVisible();

  await page.getByLabel("Login").fill("e2e.student");
  await page.getByLabel("Parol", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "kirish" }).click();
  await expect(page).toHaveURL(/\/student$/);
  await expect(page.getByRole("heading", { name: "7 kundagi yangi baholar" })).toBeVisible();

  // Back to Russian from the profile.
  await page.goto("/account/profile");
  await page.getByRole("radio", { name: "Русский" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.getByRole("heading", { name: "Безопасность" })).toBeVisible();
});
