import { test } from "@playwright/test";

/**
 * Captures README screenshots from the running app (run after ingesting the real UL data):
 *   SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts --project=desktop
 */
test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 to capture");
const out = (n: string) => `../docs/screenshots/${n}.png`;

test("capture screenshots", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: out("landing") });
  await page.goto("/chat?q=" + encodeURIComponent(process.env.SCREENSHOT_QUESTION || "How is QCA calculated?"));
  await page.getByRole("region", { name: "Sources" }).waitFor({ timeout: 90_000 });
  await page.screenshot({ path: out("chat") });
  await page.getByRole("region", { name: "Sources" }).getByRole("button").first().click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: out("citation-preview") });
  await page.keyboard.press("Escape");
  await page.goto("/explorer");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: out("explorer") });
  await page.goto("/tools");
  await page.waitForTimeout(1000);
  await page.screenshot({ path: out("tools-qca") });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/chat");
  await page.waitForTimeout(800);
  await page.screenshot({ path: out("chat-dark") });
});
