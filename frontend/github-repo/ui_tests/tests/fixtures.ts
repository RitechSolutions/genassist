import { test as base } from '@playwright/test';

export const test = base.extend({
  page: async ({ page }, use) => {
    
    await page.goto('/login');
    await page.waitForTimeout(2000);
    await page.getByRole('textbox', { name: 'Username or Email' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('genadmin');
    await page.waitForTimeout(2000);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/dashboard');

    await use(page); 
  },
});

export { expect } from '@playwright/test';
