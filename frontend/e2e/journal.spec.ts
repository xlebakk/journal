import { expect, test } from "@playwright/test";

import { login } from "./helpers";

test("teacher fills a lesson; the grade and the average appear in the journal", async ({
  page,
}) => {
  await login(page, "e2e.teacher");
  await expect(page).toHaveURL(/\/teacher$/);

  // «Сегодня» lists today's lessons with links to the lesson page.
  await page
    .getByRole("link", { name: /Физика/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/teacher\/journal\/lessons\//);
  await expect(page.getByRole("heading", { name: /Физика/ })).toBeVisible();

  await page.getByLabel("Тема").fill("Законы Ньютона");
  await page.getByLabel("Тема").blur();
  await expect(page.getByText(/Сохранено · \d\d:\d\d/)).toBeVisible();

  const input = page.getByLabel("Оценка для Алиев Ф.");
  await input.fill("150");
  await expect(input).toHaveAttribute("aria-invalid", "true");
  await input.fill("92");
  await input.press("Enter");
  await expect(page.getByRole("button", { name: "92" })).toBeVisible();

  await page.getByRole("button", { name: "завершить занятие" }).click();
  await expect(page.getByText("Занятие проведено")).toBeVisible();

  await page.getByRole("link", { name: /к журналу/ }).click();
  await expect(page).toHaveURL(/\/teacher\/journal\?course=/);
  const grid = page.getByRole("grid");
  await expect(grid.getByText("92", { exact: true }).first()).toBeVisible();
  await expect(grid.getByText("92.00")).toBeVisible();
  await expect(grid.getByText("100%")).toBeVisible();
});
