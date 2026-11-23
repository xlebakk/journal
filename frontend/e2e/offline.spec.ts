import { expect, test } from "@playwright/test";

import { login } from "./helpers";

test("without network the teacher keeps working; the changes reach the server later", async ({
  page,
  context,
}) => {
  await login(page, "e2e.teacher");
  await page
    .getByRole("link", { name: /Математика/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/teacher\/journal\/lessons\//);
  await expect(page.getByRole("heading", { name: /Математика/ })).toBeVisible();

  await context.setOffline(true);
  await expect(page.getByText(/^Нет сети\. Можно продолжать/)).toBeVisible();

  // Stage 19: only «был» and «н»; an absent student gets no grade, so the grade goes alone
  // (an offline «н» is covered by the queue unit test).
  const input = page.getByLabel("Оценка для Алиев Ф.");
  await input.fill("77");
  await input.press("Enter");
  await page.getByLabel("Тема").fill("Производная");
  await page.getByLabel("Тема").blur();

  // On the screen at once, waiting in the queue; finishing the lesson needs the network.
  await expect(page.getByText("Не отправлено: 2")).toBeVisible();
  await expect(page.getByRole("button", { name: "77" })).toBeVisible();
  await expect(page.getByRole("button", { name: "завершить занятие" })).toBeDisabled();

  await context.setOffline(false);
  // The bar goes away only when everything is on the server.
  await expect(page.getByRole("region", { name: "Изменения без сети" })).toBeHidden({
    timeout: 20_000,
  });

  await page.reload();
  await expect(page.getByRole("button", { name: "77" })).toBeVisible();
  await expect(page.getByLabel("Тема")).toHaveValue("Производная");
});
