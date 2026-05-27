/**
 * Drive a full job: login → upload → preview → submit → poll until terminal.
 * Polls /jobs/{id} directly so we don't depend on DOM scraping.
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const base = process.env.BASE_URL || "http://localhost:5173";
const password = process.env.PW || "inform";
const csvPath =
  process.env.CSV || "/workspaces/nomenclator/backend/tests/test_input_cargos.csv";
const subsetN = process.env.SUBSET_N || "5";
const dryRun = process.env.DRY_RUN === "1";
const maxPollSec = Number(process.env.MAX_POLL_SEC || "180");

mkdirSync("screenshots", { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
const page = await ctx.newPage();

page.on("pageerror", (e) => console.log("[pageerror]", e.message));
page.on("response", async (r) => {
  const u = r.url();
  if (u.endsWith("/auth") || u.endsWith("/jobs/preview") || u.includes("/commit")) {
    console.log(`<- ${r.status()} ${r.request().method()} ${u.replace(base, "")}`);
  }
});

// 1. Login
await page.goto(base + "/", { waitUntil: "networkidle" });
await page.getByPlaceholder("Enter password").fill(password);
await page.getByRole("button", { name: "Sign in" }).click();
await page
  .waitForResponse((r) => r.url().endsWith("/me") && r.status() === 200, { timeout: 5000 })
  .catch(() => {});

// 2. Upload + subset
console.log(`\n[subset_n=${subsetN}, dry_run=${dryRun}]`);
await page.locator('input[type="file"]').first().setInputFiles(csvPath);

// The row-subset Select is a Base UI custom widget. Click the trigger button
// (whose visible text is the current value, "All rows") and pick "First N rows".
try {
  await page.getByText("All rows", { exact: true }).click({ timeout: 2000 });
  await page.getByText("First N rows", { exact: true }).click({ timeout: 2000 });
  const nInput = page.locator('input[type="number"][placeholder="N"]').first();
  await nInput.fill(subsetN);
  console.log(`subset selected: first_n / ${subsetN}`);
} catch (e) {
  console.log(`subset selection failed (${e.message}) — falling back to All rows`);
}

// Dry-run toggle if requested
if (dryRun) {
  const dryToggle = page.locator('input[type="checkbox"]').first();
  if (await dryToggle.count()) await dryToggle.check();
}

// 3. Preview — register the listener BEFORE clicking to avoid a race
const previewPromise = page.waitForResponse((r) => r.url().endsWith("/jobs/preview"), {
  timeout: 60000,
});
await page.getByRole("button", { name: "Preview clusters" }).click();
const previewResp = await previewPromise;
const previewBody = await previewResp.json();
const jobId = previewBody.job_id;
console.log(`preview ok: job_id=${jobId}, clusters=${previewBody.cluster_count}`);

await page.locator('[data-testid="preview-card"]').waitFor({ timeout: 10000 });
await page.screenshot({ path: "screenshots/real_preview.png", fullPage: true });

// 4. Submit
console.log("\n[submit]");
const commitPromise = page.waitForResponse(
  (r) => r.url().includes("/commit"),
  { timeout: 15000 }
);
await page.locator('[data-testid="btn-submit"]').click();
const commitResp = await commitPromise;
const commitStatus = commitResp.status();
const commitBody = await commitResp.json().catch(() => ({}));

if (commitStatus >= 400) {
  console.log("commit FAILED:", JSON.stringify(commitBody, null, 2));
  await page.waitForTimeout(500);
  await page.screenshot({ path: "screenshots/real_error.png", fullPage: true });
  await browser.close();
  process.exit(1);
}

console.log(`commit ok: status=${commitStatus}`);

// 5. Poll job status via API
console.log("\n[polling]");
const cookies = await ctx.cookies();
const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
const fetchJob = () =>
  fetch(`http://localhost:8000/jobs/${jobId}`, {
    headers: { Cookie: cookieHeader },
  }).then((r) => r.json());

const start = Date.now();
let last = "";
let final = null;
while ((Date.now() - start) / 1000 < maxPollSec) {
  const j = await fetchJob();
  const elapsed = Math.floor((Date.now() - start) / 1000);
  const prog = j.progress
    ? `${j.progress.clusters_resolved}/${j.progress.clusters_total} resolved`
    : "";
  const line = `t+${elapsed}s status=${j.status} ${prog} cost=$${(j.actual_cost_usd || 0).toFixed(4)}`;
  if (line !== last) {
    console.log("  " + line);
    last = line;
  }
  if (["completed", "failed", "cancelled"].includes(j.status)) {
    final = j;
    break;
  }
  await new Promise((r) => setTimeout(r, 3000));
}

if (!final) {
  console.log("TIMED OUT");
  await page.screenshot({ path: "screenshots/real_timeout.png", fullPage: true });
  await browser.close();
  process.exit(2);
}

console.log(`\nFINAL: ${final.status}, cost=$${(final.actual_cost_usd || 0).toFixed(4)}`);
await page.waitForTimeout(1500);
await page.screenshot({ path: "screenshots/real_final.png", fullPage: true });

if (final.status === "completed") {
  // Try to download the result CSV
  const dl = await fetch(`http://localhost:8000/jobs/${jobId}/download`, {
    headers: { Cookie: cookieHeader },
  });
  if (dl.ok) {
    const text = await dl.text();
    console.log("\n=== first 800 chars of result CSV ===");
    console.log(text.slice(0, 800));
  } else {
    console.log("download HTTP", dl.status);
  }
}

await browser.close();
