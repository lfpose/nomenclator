/**
 * Asserts the cluster-preview UX contract end-to-end. Exits non-zero on
 * regression so it can be wired into a CI / dev loop:
 *   pnpm assert   (from e2e/)
 *
 * Asserts:
 *   1. Login with dev password succeeds.
 *   2. Preview returns 200 and a parseable response.
 *   3. Each cluster card renders a non-empty representative.
 *   4. Each cluster card renders a non-empty member-count.
 *   5. Summary cluster-count equals the API value.
 *   6. Expanding a cluster reveals N member rows.
 *   7. Raw debug toggle reveals the JSON.
 *   8. No React "missing key" console errors during the flow.
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const base = process.env.BASE_URL || "http://localhost:5173";
const password = process.env.PW || "inform";
const csvPath =
  process.env.CSV || "/workspaces/nomenclator/backend/tests/test_input_cargos.csv";

mkdirSync("screenshots", { recursive: true });

const failures = [];
const consoleErrors = [];

function assert(cond, msg) {
  if (!cond) {
    failures.push(msg);
    console.error("  FAIL:", msg);
  } else {
    console.log("  ok  :", msg);
  }
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
const page = await ctx.newPage();

page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`));

// 1. Login
console.log("\n[1] Login");
await page.goto(base + "/", { waitUntil: "networkidle" });
await page.getByPlaceholder("Enter password").fill(password);
const authPromise = page.waitForResponse(
  (r) => r.url().endsWith("/auth") && r.request().method() === "POST"
);
await page.getByRole("button", { name: "Sign in" }).click();
const authResp = await authPromise;
assert(authResp.status() === 200, `auth POST returned ${authResp.status()}`);
await page
  .waitForResponse((r) => r.url().endsWith("/me") && r.status() === 200, { timeout: 5000 })
  .catch(() => {});

// 2. Upload + preview
console.log("\n[2] Upload + preview");
await page.locator('input[type="file"]').first().setInputFiles(csvPath);
const previewPromise = page.waitForResponse((r) => r.url().endsWith("/jobs/preview"), {
  timeout: 60000,
});
await page.getByRole("button", { name: "Preview clusters" }).click();
const previewResp = await previewPromise;
assert(previewResp.status() === 200, `preview returned ${previewResp.status()}`);
const previewJson = await previewResp.json();

await page.locator('[data-testid="preview-card"]').waitFor({ timeout: 10000 });
await page.screenshot({ path: "screenshots/assert_preview.png", fullPage: true });

// 3 + 4. Cluster cards
console.log("\n[3+4] Cluster cards content");
const cards = page.locator('[data-testid="cluster-card"]');
const cardCount = await cards.count();
assert(cardCount === previewJson.top_clusters.length, `expected ${previewJson.top_clusters.length} cards, got ${cardCount}`);

for (let i = 0; i < cardCount; i++) {
  const card = cards.nth(i);
  const rep = (await card.locator('[data-testid="cluster-representative"]').innerText()).trim();
  const mc = (await card.locator('[data-testid="cluster-member-count"]').innerText()).trim();
  assert(rep.length > 0, `card[${i}] representative is non-empty`);
  assert(/\d+\s+members?/.test(mc), `card[${i}] member-count looks like "N members" (got "${mc}")`);
}

// 5. Summary cluster-count
console.log("\n[5] Summary matches API");
const summaryText = await page.locator('[data-testid="summary-cluster-count"]').innerText();
assert(
  summaryText.replace(/[^\d]/g, "") === String(previewJson.cluster_count),
  `summary cluster-count "${summaryText}" matches API ${previewJson.cluster_count}`
);

// 6. Expand cluster reveals members
console.log("\n[6] Expand cluster reveals members");
const firstCard = cards.first();
await firstCard.locator("button").first().click();
const memberList = firstCard.locator('[data-testid="cluster-members"]');
await memberList.waitFor({ timeout: 2000 });
const memberCount = await memberList.locator("> div").count();
const expectedMembers = previewJson.top_clusters[0].members.length;
assert(
  memberCount === expectedMembers,
  `expanded card shows ${expectedMembers} member rows (got ${memberCount})`
);
await page.screenshot({ path: "screenshots/assert_expanded.png", fullPage: true });

// 7. Raw debug toggle
console.log("\n[7] Raw debug toggle");
await page.locator('[data-testid="toggle-raw"]').click();
const raw = page.locator('[data-testid="raw-response"]');
await raw.waitFor({ timeout: 1000 });
const rawText = await raw.innerText();
assert(rawText.includes('"job_id"'), "raw response contains job_id");
assert(rawText.includes('"size_distribution"'), "raw response contains size_distribution");

// 8. No "missing key" warnings
console.log("\n[8] No missing-key warnings");
const keyWarnings = consoleErrors.filter((e) => /unique "key" prop/.test(e));
assert(keyWarnings.length === 0, `no React missing-key warnings (saw ${keyWarnings.length})`);

await browser.close();

console.log(`\n=== ${failures.length === 0 ? "PASS" : "FAIL"} ===`);
if (failures.length) {
  failures.forEach((f) => console.log(" - " + f));
  process.exit(1);
}
