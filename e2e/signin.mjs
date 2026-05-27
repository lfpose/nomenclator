import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const base = process.env.BASE_URL || "http://localhost:5173";
const password = process.env.PW || "inform";

mkdirSync("screenshots", { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();

const errs = [];
const reqFails = [];
page.on("console", (m) => m.type() === "error" && errs.push(m.text()));
page.on("pageerror", (e) => errs.push(`pageerror: ${e.message}`));
page.on("response", (r) => {
  if (r.status() >= 400) reqFails.push(`${r.status()} ${r.request().method()} ${r.url()}`);
});

await page.goto(base + "/", { waitUntil: "networkidle" });
await page.screenshot({ path: "screenshots/before_login.png", fullPage: true });

await page.getByPlaceholder("Enter password").fill(password);
const authResp = page.waitForResponse(
  (r) => r.url().endsWith("/auth") && r.request().method() === "POST"
);
await page.getByRole("button", { name: "Sign in" }).click();
const r = await authResp;
console.log(`auth POST -> ${r.status()}`);

await page
  .waitForResponse((r) => r.url().endsWith("/me") && r.status() === 200, { timeout: 5000 })
  .catch(() => console.log("no successful /me observed"));
await page.waitForLoadState("networkidle");
await page.screenshot({ path: "screenshots/after_login.png", fullPage: true });

const title = await page.title();
const url = page.url();
const bodyText = (await page.locator("body").innerText()).slice(0, 500);

console.log(`url: ${url}\ntitle: ${title}`);
console.log(`errors:\n${errs.length ? errs.map((e) => "  - " + e).join("\n") : "  none"}`);
console.log(
  `failed-requests:\n${reqFails.length ? reqFails.map((e) => "  - " + e).join("\n") : "  none"}`
);
console.log(`\nbody preview:\n${bodyText}`);

await browser.close();
