import { test, expect } from './fixtures';

test('User Types › Functionality', async ({ page }) => {
  await page.getByRole('button', { name: 'Admin Tools' }).click();
  await page.getByRole('link', { name: 'User Types' }).click();

  await page.getByRole('button', { name: /add new user type/i }).click();
  await page.getByRole('textbox', { name: /name/i }).fill('playwright_testify_user_type');
  await page.getByRole('button', { name: /create user type/i }).click();

  const newUserTypeRow = page.locator('tr', {
    has: page.locator('td', { hasText: 'playwright_testify_user_type' }),
  });
  await expect(newUserTypeRow).toBeVisible();
  await page.waitForTimeout(2000);
  await newUserTypeRow.getByRole('button', { name: /edit user type/i }).click();
  await page.getByRole('heading', { name: /edit user type/i }).isVisible();
  await page.getByRole('textbox', { name: /name/i }).fill('playwright_updated_user_type');
  await page.getByRole('button', { name: /update user type/i }).click();

  const updatedUserTypeRow = page.locator('tr', {
    has: page.locator('td', { hasText: 'playwright_updated_user_type' }),
  });
  await expect(updatedUserTypeRow).toBeVisible();
  await page.waitForTimeout(3000);

  await updatedUserTypeRow.getByRole('button', { name: /delete user type/i }).click();
  await page.waitForTimeout(3000);
  await page.getByRole('button', { name: /delete/i }).click();

  await page.getByText('User type deleted successfully');
  await page.waitForTimeout(3000);

  const deletedUserTypeRow = page.locator('tr', {
    has: page.locator('td', { hasText: 'playwright_updated_user_type' }),
  });
  await expect(deletedUserTypeRow).not.toBeVisible();
});
