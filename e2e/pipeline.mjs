import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const base = process.env.BASE_URL || "http://localhost:5173";
const password = process.env.PW || "inform";
const csvPath =
  process.env.CSV || "/workspaces/nomenclator/backend/tests/test_input_cargos.csv";

mkdirSync("screenshots", { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
const page = await ctx.newPage();

const errs = [];
const reqFails = [];
const previewResponses = [];
page.on("console", (m) => m.type() === "error" && errs.push(m.text()));
page.on("pageerror", (e) => errs.push(`pageerror: ${e.message}`));
page.on("response", async (r) => {
  if (r.status() >= 400) reqFails.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  if (r.url().endsWith("/jobs/preview") || r.url().includes("/recluster")) {
    try {
      previewResponses.push({ url: r.url(), status: r.status(), body: await r.json() });
    } catch {}
  }
});

// 1. Login
await page.goto(base + "/", { waitUntil: "networkidle" });
await page.getByPlaceholder("Enter password").fill(password);
const auth = page.waitForResponse(
  (r) => r.url().endsWith("/auth") && r.request().method() === "POST"
);
await page.getByRole("button", { name: "Sign in" }).click();
const authResp = await auth;
console.log(`login -> ${authResp.status()}`);
await page
  .waitForResponse((r) => r.url().endsWith("/me") && r.status() === 200, { timeout: 5000 })
  .catch(() => {});
await page.waitForTimeout(500);

// 2. Upload CSV via the hidden file input
const fileInput = page.locator('input[type="file"]').first();
await fileInput.setInputFiles(csvPath);
await page.waitForTimeout(800);
await page.screenshot({ path: "screenshots/01_uploaded.png", fullPage: true });

// 3. Click Preview clusters
const previewPromise = page.waitForResponse(
  (r) => r.url().endsWith("/jobs/preview"),
  { timeout: 60000 }
);
await page.getByRole("button", { name: "Preview clusters" }).click();
const previewResp = await previewPromise;
console.log(`preview -> ${previewResp.status()}`);

await page.waitForTimeout(1500);
await page.screenshot({ path: "screenshots/02_preview.png", fullPage: true });

// 4. Capture preview data for analysis
const previewJson = previewResponses.find((p) => p.url.endsWith("/jobs/preview"))?.body;
writeFileSync("screenshots/preview.json", JSON.stringify(previewJson, null, 2));

// 5. Inspect what's visible on screen for the cluster section
const previewSectionText = await page
  .locator('text=Preview results')
  .first()
  .locator("xpath=ancestor::*[1]")
  .innerText()
  .catch(() => "");
writeFileSync("screenshots/preview_visible_text.txt", previewSectionText);

// 6. Try to submit job (will fail with ANTHROPIC_API_KEY=test but worth seeing the UX)
const submitBtn = page
  .getByRole("button", { name: /^(Run|Commit|Submit|Start|Go)/i })
  .first();
const hasSubmit = await submitBtn.count();
console.log(`submit-like buttons found: ${hasSubmit}`);

// List all visible buttons on the page so we know what controls exist
const buttons = await page.locator("button:visible").allInnerTexts();
writeFileSync("screenshots/visible_buttons.txt", buttons.join("\n"));

console.log(`\nerrors:\n${errs.length ? errs.map((e) => "  - " + e).join("\n") : "  none"}`);
console.log(
  `failed-requests:\n${reqFails.length ? reqFails.map((e) => "  - " + e).join("\n") : "  none"}`
);

await browser.close();
console.log("\ndone. artifacts: screenshots/{01_uploaded,02_preview}.png, preview.json, visible_buttons.txt");
