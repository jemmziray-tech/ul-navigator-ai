import { expect, test } from "@playwright/test";

const DISCLAIMER = "UL Navigator AI is an independent student-led project and is not an official University of Limerick service.";

test.describe("core workflows", () => {
  test("landing page shows hero, disclaimer and live stats", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("University of Limerick");
    await expect(page.getByText(DISCLAIMER).first()).toBeVisible();
    await expect(page.getByText("Indexed sources")).toBeVisible();
    await expect(page.getByText("Searchable passages")).toBeVisible();
  });

  test("ask from landing -> streamed, cited answer -> source preview -> history", async ({ page }) => {
    await page.goto("/");
    const question = "How many books can undergraduate students borrow?";
    await page.getByLabel("Ask a question about UL").fill(question);
    await page.getByRole("button", { name: "Ask" }).click();
    await expect(page).toHaveURL(/\/chat/);
    await expect(page.getByText(question)).toBeVisible();
    const sources = page.getByRole("region", { name: "Sources" });
    await expect(sources).toBeVisible({ timeout: 30_000 });
    const firstCard = sources.getByRole("button").first();
    await firstCard.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("Supporting passage")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(page.getByRole("button", { name: "Copy answer" })).toBeVisible();
    await page.getByRole("button", { name: "Helpful", exact: true }).click();
    await expect(page.getByRole("button", { name: "Helpful", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("navigation", { name: "Conversation history" }).getByText(question)).toBeVisible();
  });

  test("insufficient evidence is acknowledged, not invented", async ({ page }) => {
    await page.goto("/chat");
    await page.getByLabel("Your question").fill("What is the best pizza recipe with pineapple?");
    await page.keyboard.press("Enter");
    await expect(page.getByText("Not enough evidence")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/won't guess/)).toBeVisible();
  });

  test("follow-up suggestion and new conversation", async ({ page }) => {
    await page.goto("/chat?q=" + encodeURIComponent("What are the library opening hours?"));
    const followups = page.getByLabel("Suggested follow-up questions");
    await expect(followups).toBeVisible({ timeout: 30_000 });
    await followups.getByRole("button").first().click();
    await expect(page.locator("ol > li")).toHaveCount(4, { timeout: 30_000 });
    await page.getByRole("button", { name: "New conversation" }).click();
    await expect(page.getByRole("heading", { name: "How can I help you at UL?" })).toBeVisible();
  });

  test("dark mode toggle", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Switch to (dark|light) mode/ }).click();
    const cls = await page.locator("html").getAttribute("class");
    expect(cls).toMatch(/dark|light/);
  });

  test("knowledge explorer search, filter and preview", async ({ page }) => {
    await page.goto("/explorer");
    await expect(page.getByText(/\d+ sources?/)).toBeVisible();
    await page.getByLabel("Category").selectOption("fees");
    await expect(page.getByText("1 source")).toBeVisible();
    await page.locator("main button.rounded-2xl").first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("QCA calculator computes from UL grade points", async ({ page }) => {
    await page.goto("/tools");
    for (let i = 1; i <= 5; i++) await page.getByLabel(`Module ${i} grade`).selectOption("A1");
    await expect(page.locator("[aria-live=polite]").filter({ hasText: "4.00" })).toBeVisible();
    await expect(page.getByText("First class honours")).toBeVisible();
  });

  test("student tools tabs load", async ({ page }) => {
    await page.goto("/tools");
    await page.getByRole("tab", { name: /International checklist/ }).click();
    await expect(page.getByText("Your progress")).toBeVisible();
    await page.getByRole("tab", { name: /Module search/ }).click();
    await page.getByLabel("Module code or name").fill("NB4012");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByText(/NB4012/).first()).toBeVisible();
  });

  test("admin requires login and rejects bad credentials", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Admin sign in" })).toBeVisible();
    await page.getByLabel("Password").fill("wrong-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
  });

  test("admin dashboard with valid credentials", async ({ page }) => {
    test.skip(!process.env.E2E_ADMIN_PASSWORD, "set E2E_ADMIN_PASSWORD to run");
    await page.goto("/admin");
    await page.getByLabel("Password").fill(process.env.E2E_ADMIN_PASSWORD!);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Indexed documents")).toBeVisible();
    await page.getByRole("button", { name: "Ingestion jobs" }).click();
    await expect(page.getByText(/upload|crawl|demo/i).first()).toBeVisible();
  });
});
