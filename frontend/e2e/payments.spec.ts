import { expect, test } from "@playwright/test";

import { login, logout, totp } from "./helpers";

const ADMIN4_SECRET = "ONSWG4TFORZWK3TUMVZXI5DFON2HE2LO";

test("admin prices the group and bills the month; the student sees the debt, then pays", async ({
  page,
}) => {
  await login(page, "e2e.admin4");
  await page.getByLabel("Код").fill(totp(ADMIN4_SECRET));
  await page.getByRole("button", { name: "подтвердить" }).click();
  await expect(page).toHaveURL(/\/admin$/);

  await page.getByRole("link", { name: "Оплаты" }).first().click();
  await page.getByRole("tab", { name: "Цены и начисления" }).click();
  await page.getByLabel("Цена в месяц для 11-М вечерняя").fill("500000");
  // Billing reads the saved price: wait for the server to have it.
  const saved = page.waitForResponse(
    (r) => r.url().includes("/api/v1/admin/payments/groups/") && r.request().method() === "PUT",
  );
  await page.getByRole("button", { name: "сохранить" }).first().click();
  expect((await saved).status()).toBe(204);
  await page.getByRole("button", { name: /^начислить за/ }).click();
  await expect(page.getByRole("status")).toHaveText(/Начислено: 1/);

  await page.getByRole("tab", { name: "Ученики" }).click();
  await expect(page.getByText(/Должников: 1, на сумму 500\s000 сомони/)).toBeVisible();
  await logout(page);

  await login(page, "e2e.student");
  await expect(page.getByText(/Задолженность за обучение: 500\s000 сомони/)).toBeVisible();
  await page.getByRole("link", { name: "подробнее" }).click();
  await expect(page).toHaveURL(/\/student\/payments$/);
  // The server refuses the administrator's ledger, whatever the client shows.
  expect((await page.request.get("/api/v1/admin/payments/students")).status()).toBe(403);
});
