import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { argv } from "node:process";

const base = process.env.BASE_URL || "http://localhost:5173";
const routes = argv.slice(2);
const targets = routes.length ? routes : ["/", "/about", "/docs"];

mkdirSync("screenshots", { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();

const results = [];

for (const route of targets) {
  const errs = [];
  const warns = [];
  const reqFails = [];

  page.removeAllListeners("console");
  page.removeAllListeners("pageerror");
  page.removeAllListeners("requestfailed");

  page.on("console", (msg) => {
    const type = msg.type();
    const text = msg.text();
    if (type === "error") errs.push(text);
    else if (type === "warning") warns.push(text);
  });
  page.on("pageerror", (e) => errs.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) =>
    reqFails.push(`${r.method()} ${r.url()} -> ${r.failure()?.errorText}`)
  );
  page.on("response", (r) => {
    if (r.status() >= 400) reqFails.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  });

  const url = base + route;
  const resp = await page.goto(url, { waitUntil: "networkidle", timeout: 15000 }).catch((e) => {
    errs.push(`goto failed: ${e.message}`);
    return null;
  });

  const status = resp ? resp.status() : "n/a";
  const title = await page.title().catch(() => "");
  const safe = route.replace(/[^a-z0-9]+/gi, "_") || "root";
  const shotPath = `screenshots/${safe}.png`;
  await page.screenshot({ path: shotPath, fullPage: true });

  results.push({ route, url, status, title, errs, warns, reqFails, shot: shotPath });
}

await browser.close();

const out = results
  .map(
    (r) =>
      `\n=== ${r.route} (${r.status}) ===\n` +
      `title: ${r.title}\n` +
      `shot: ${r.shot}\n` +
      (r.errs.length ? `errors:\n  - ${r.errs.join("\n  - ")}\n` : "errors: none\n") +
      (r.reqFails.length ? `failed-requests:\n  - ${r.reqFails.join("\n  - ")}\n` : "") +
      (r.warns.length ? `warnings:\n  - ${r.warns.join("\n  - ")}\n` : "")
  )
  .join("");

console.log(out);
writeFileSync("screenshots/report.txt", out);
