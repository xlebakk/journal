import { expect, test, type Page } from "@playwright/test";

import { login, logout } from "./helpers";

// e2e serves the production build with the production headers (vite preview reads them from
// infra/caddy/common.caddy). Any Content-Security-Policy violation on the main screens fails.
async function watchViolations(page: Page): Promise<string[]> {
  const violations: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy|Refused to/i.test(message.text())) violations.push(message.text());
  });
  // Runs in the page (a string: the e2e files are typed without the DOM library).
  await page.addInitScript(`document.addEventListener("securitypolicyviolation", (event) =>
    console.error("Refused to load: " + event.violatedDirective + " " + event.blockedURI));`);
  return violations;
}

test("the main screens run under the production CSP without violations", async ({ page }) => {
  const violations = await watchViolations(page);

  const response = await page.goto("/login");
  const csp = response?.headers()["content-security-policy"] ?? "";
  expect(csp).toContain("script-src 'self'");
  expect(csp).toContain("frame-ancestors 'none'");

  await login(page, "e2e.student");
  await expect(page).toHaveURL(/\/student$/);
  for (const path of ["/student/diary", "/student/grades", "/student/tests", "/student/schedule"]) {
    await page.goto(path);
    await expect(page.getByRole("heading").first()).toBeVisible();
  }
  await logout(page);

  await login(page, "e2e.teacher");
  await expect(page).toHaveURL(/\/teacher$/);
  for (const path of [
    "/teacher/journal",
    "/teacher/exams",
    "/teacher/reports",
    "/teacher/schedule",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading").first()).toBeVisible();
  }

  expect(violations).toEqual([]);
});
