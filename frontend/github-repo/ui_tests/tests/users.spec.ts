import { test, expect } from "./fixtures";

test("Users › Functionality", async ({ page }) => {
  const now = new Date();
  const suffix = now.getTime();
  const longDay = now.toLocaleString("en-US", { weekday: "long" });
  const day2Chars = longDay.slice(0, 2).toUpperCase();
  const username = `playwright_${suffix}_${day2Chars}`;
  const email = `playwright_${suffix}_${day2Chars}@example.com`;

  await page.getByRole("button", { name: "Admin Tools" }).click();
  await page.getByRole("link", { name: "Users" }).click();

  await page.getByRole("button", { name: "Add New User" }).click();
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByRole("textbox", { name: "Email" }).fill(email);
  await page.getByRole("combobox").click();
  await page.getByRole("option", { name: "interactive" }).click();
  await page
    .getByRole("textbox", { name: "Password" })
    .fill("frank123" + suffix);
  await page.getByRole("checkbox", { name: "api" }).check();

  page.getByRole("button", { name: /create user/i }).click();
  await page.waitForTimeout(1000);

  await expect(
    page.getByRole("heading", { name: "Create New User" })
  ).toBeHidden();

  const userRow = page
    .locator("tr", {
      has: page.locator("td", { hasText: username }),
    })
    .filter({
      has: page.locator("td", { hasText: email }),
    });
  await expect(userRow).toBeVisible();

  await page.waitForTimeout(2000);
  await userRow.getByRole("button", { name: "Edit User" }).click();
  await expect(page.getByRole("heading", { name: "Edit User" })).toBeVisible();

  await page.getByRole("textbox", { name: "New Password" }).fill("NewPass456");

  await page.getByRole("checkbox", { name: "api" }).check();
  await page.getByRole("combobox").click();
  await page
    .getByRole("option", { name: "console" })
    .locator("span")
    .first()
    .click();

  await page.getByRole("button", { name: /update user/i }).click();
  await page.waitForTimeout(3000);

  await expect(page.getByRole("heading", { name: "Edit User" })).toBeHidden();

  await expect(userRow).toContainText(username);
  await expect(page.getByText("User updated successfully")).toBeVisible();
  await page.waitForTimeout(5000);
});
