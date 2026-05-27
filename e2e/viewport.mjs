/**
 * Captures viewport-only screenshots (no full page) to verify the SPA-no-scroll
 * layout fits within the configured viewport at common sizes.
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const base = process.env.BASE_URL || "http://localhost:5173";
const password = process.env.PW || "inform";
const csvPath =
  process.env.CSV || "/workspaces/nomenclator/backend/tests/test_input_cargos.csv";

mkdirSync("screenshots", { recursive: true });

const sizes = [
  { name: "macbook", w: 1440, h: 900 },
  { name: "laptop", w: 1280, h: 800 },
  { name: "small", w: 1100, h: 700 },
];

const browser = await chromium.launch();
for (const { name, w, h } of sizes) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByPlaceholder("Enter password").fill(password);
  const auth = page.waitForResponse(
    (r) => r.url().endsWith("/auth") && r.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Sign in" }).click();
  await auth;
  await page
    .waitForResponse((r) => r.url().endsWith("/me") && r.status() === 200, { timeout: 5000 })
    .catch(() => {});

  // Idle viewport
  await page.screenshot({ path: `screenshots/vp_${name}_idle.png`, fullPage: false });

  // Upload + preview
  await page.locator('input[type="file"]').first().setInputFiles(csvPath);
  const previewPromise = page.waitForResponse((r) => r.url().endsWith("/jobs/preview"), {
    timeout: 60000,
  });
  await page.getByRole("button", { name: "Preview clusters" }).click();
  await previewPromise;
  await page.locator('[data-testid="preview-card"]').waitFor({ timeout: 10000 });
  await page.waitForTimeout(200);

  await page.screenshot({ path: `screenshots/vp_${name}_preview.png`, fullPage: false });

  // Check page scrollability (body should not exceed viewport)
  const overflow = await page.evaluate(() => ({
    docH: document.documentElement.scrollHeight,
    winH: window.innerHeight,
    bodyH: document.body.scrollHeight,
  }));
  console.log(
    `${name} (${w}x${h}): doc=${overflow.docH} win=${overflow.winH} body=${overflow.bodyH} -> ${
      overflow.docH > overflow.winH ? "PAGE SCROLLS" : "fits"
    }`
  );

  await ctx.close();
}
await browser.close();
