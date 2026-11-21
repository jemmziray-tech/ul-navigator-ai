import { expect, test } from "@playwright/test";

test("mobile navigation and chat drawer", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("navigation", { name: "Mobile" }).getByText("Ask AI").click();
  await expect(page).toHaveURL(/\/chat/);
  await page.getByRole("button", { name: "Open conversation history" }).click();
  await expect(page.getByRole("button", { name: "New conversation" })).toBeVisible();
});
