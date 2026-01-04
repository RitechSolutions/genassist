import { test, expect } from './fixtures';

test('Login', async ({ page }) => {
    await page.waitForTimeout(5000);

    await expect(page.getByRole('heading', { name: 'Welcome to GenAssist' })).toBeVisible();
  });