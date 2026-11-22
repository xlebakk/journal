// SPEC §15: Lighthouse Accessibility ≥ 95 and Performance ≥ 90 on the login page and the
// student's home page. The production build, through whatever serves it (vite preview or Caddy):
//   BASE_URL=https://localhost STUDENT_LOGIN=… STUDENT_PASSWORD=… node scripts/lighthouse.mjs
// CHROME_PATH picks the browser; self-signed certificates (Caddy's internal CA) are accepted.
// The student page is measured in the same tab after a real login (storage is not reset).
import * as chromeLauncher from "chrome-launcher";
import lighthouse from "lighthouse";
import puppeteer from "puppeteer-core";

const base = (process.env.BASE_URL ?? "http://localhost:5174").replace(/\/+$/, "");
const MIN = { accessibility: 0.95, performance: 0.9 };

/** Logs in through the real login form, so the page holds the session like a student's. */
async function loginAsStudent(page) {
  const login = process.env.STUDENT_LOGIN;
  const password = process.env.STUDENT_PASSWORD;
  if (!login || !password) throw new Error("STUDENT_LOGIN and STUDENT_PASSWORD are required");
  await page.goto(`${base}/login`, { waitUntil: "networkidle0" });
  await page.type("input[autocomplete=username]", login);
  await page.type("input[type=password]", password);
  await page.click("button[type=submit]");
  // The app routes client-side: / → /student once the session is there.
  await page
    .waitForFunction("location.pathname.startsWith('/student')", { timeout: 15_000 })
    .catch(() => {
      throw new Error(`student login failed: still on ${page.url()}`);
    });
}

// Job logs need a login to read; in CI the summary also goes to public annotations.
const report = [];
function say(line) {
  console.log(line);
  report.push(line);
}

// Like Lighthouse CI: several runs, the median counts — the first run in a cold browser
// (empty code caches) is an outlier, not the page.
const RUNS = Number(process.env.LIGHTHOUSE_RUNS ?? 3);

async function once(page, path, keepSession) {
  const { lhr } = await lighthouse(
    `${base}${path}`,
    { onlyCategories: Object.keys(MIN), disableStorageReset: keepSession, logLevel: "error" },
    undefined,
    page,
  );
  if (lhr.runtimeError) throw new Error(`${path}: ${lhr.runtimeError.message}`);
  if (lhr.finalDisplayedUrl.replace(base, "") !== path) {
    throw new Error(`${path} redirected to ${lhr.finalDisplayedUrl}: not logged in?`);
  }
  return lhr;
}

async function audit(page, path, keepSession) {
  const runs = [];
  for (let i = 0; i < RUNS; i += 1) runs.push(await once(page, path, keepSession));
  let ok = true;
  for (const [category, min] of Object.entries(MIN)) {
    const scores = runs.map((lhr) => lhr.categories[category].score ?? 0);
    const sorted = [...scores].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    const pass = median >= min;
    ok &&= pass;
    const all = scores.map((x) => Math.round(x * 100)).join("/");
    say(
      `${pass ? "✓" : "✗"} ${path} ${category} ${Math.round(median * 100)} (runs ${all}, min ${min * 100})`,
    );
    if (!pass) {
      const lhr = runs[scores.indexOf(median)];
      for (const ref of lhr.categories[category].auditRefs) {
        const item = lhr.audits[ref.id];
        if (ref.weight > 0 && item.score !== null && item.score < 0.9) {
          say(`    ${item.id}: ${item.displayValue ?? ""} ${item.title}`);
        }
      }
    }
  }
  return ok;
}

const chrome = await chromeLauncher.launch({
  chromeFlags: ["--headless=new", "--no-sandbox", "--ignore-certificate-errors"],
});
const browser = await puppeteer.connect({ browserURL: `http://127.0.0.1:${chrome.port}` });
try {
  const page = await browser.newPage();
  const results = [await audit(page, "/login", false)];
  await loginAsStudent(page);
  results.push(await audit(page, "/student", true));
  if (results.includes(false)) process.exitCode = 1;
} catch (error) {
  say(`✗ ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
} finally {
  if (process.env.GITHUB_ACTIONS) {
    const kind = process.exitCode ? "error" : "notice";
    console.log(`::${kind} title=Lighthouse::${report.join("%0A")}`);
  }
  await browser.disconnect();
  await chrome.kill();
}
