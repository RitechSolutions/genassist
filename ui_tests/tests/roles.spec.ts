import { test, expect } from './fixtures';


test("Roles › Functionality", async ({ page }) => {

  const timestamp = Date.now();
  const roleName = `playwright_role_${timestamp}`;
  const updatedRoleName = `updated_role_${timestamp}`;

  await page.getByRole("button", { name: "Admin Tools" }).click();
  await page.getByRole("link", { name: "Roles" }).click();

  await page.getByRole("button", { name: /add new role/i }).click();
  await page
    .getByRole("textbox", { name: /name/i })
    .fill(roleName);
  await page.getByRole("switch", { name: /active/i }).click();

  const firstCheckbox = page.locator('input[type="checkbox"]').first();
  if (await firstCheckbox.isVisible()) {
    await page.waitForTimeout(1000);
    await page.getByRole('checkbox', { name: 'read:user', exact: true }).click();
  }

  await Promise.all([
    page.waitForResponse(
      (res) => res.url().includes("/roles") && [200, 201].includes(res.status())
    ),
    page.getByRole("button", { name: /create role/i }).click(),
  ]);

  const newRoleRow = page.locator("tr", {
    has: page.locator("td", { hasText: roleName }),
  });
  await page.waitForTimeout(2000);
  await expect(newRoleRow).toBeVisible();


  await newRoleRow.getByRole('button', { name: /edit role/i }).click();
  await page.getByRole('heading', { name: /edit role/i }).isVisible();
  await page.getByRole('textbox', { name: /name/i }).fill(updatedRoleName);
  await Promise.all([
    page.waitForResponse((res) =>
      res.url().includes('/roles') && res.status() === 200
    ),
    page.getByRole('button', { name: /update role/i }).click(),
  ]);

  const updatedRoleRow = page.locator('tr', {
    has: page.locator('td', { hasText: updatedRoleName}),
  });
  await page.waitForTimeout(5000);
  await expect(updatedRoleRow).toBeVisible();

   await updatedRoleRow.locator('button[title="Delete Role"]').click();

   await page.getByRole("button", { name: /delete/i }).click();

   await page.waitForResponse(res =>
     res.url().includes("/roles/") && res.request().method() === "DELETE" && res.status() === 200
   );

   await expect(page.getByText("Role deleted successfully")).toBeVisible();
   await expect(updatedRoleRow).not.toBeVisible();
  await page.waitForTimeout(2000);
});
