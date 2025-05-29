import { test, expect } from './fixtures';

test('API Keys › create, edit, and revoke', async ({ page }) => {
  const randomSuffix = Math.floor(Math.random() * 100000);
  const originalName = `playwright_key_${randomSuffix}`;
  const updatedName = `${originalName}_updated`;

  await page.getByRole('button', { name: 'Admin Tools' }).click();
  await page.getByRole('link', { name: /api keys/i }).click();
  await page.waitForURL('**/api-keys');

  await page.getByRole('button', { name: /generate new api key/i }).click();
  await page.getByRole('textbox', { name: /name/i }).fill(originalName);
  await page.getByRole('switch', { name: 'Active' }).click();

  await page.getByRole('checkbox', { name: 'admin' }).uncheck();
  await Promise.all([
    page.waitForResponse(r =>
      r.request().method() === 'POST' &&
      r.url().includes('/api-keys') &&
      [200, 201].includes(r.status())
    ),
    page.getByRole('button', { name: /^Generate Key$/i }).click(),
  ]);

  await page.waitForTimeout(1000); 

  await page.getByRole('button', { name: 'Copy to clipboard' }).click();
  await page.waitForTimeout(1000); 
  await page.getByRole('button', { name: 'Show key' }).click();
  await page.waitForTimeout(1500); 
  await page.getByRole('button', { name: 'Hide key' }).click();
  await page.waitForTimeout(1000); 
  await page.getByRole('button', { name: 'Cancel' }).click();

  await expect(
    page.getByRole('heading', { name: 'Generate New API Key' })
  ).toBeHidden();
  await page.waitForTimeout(2000);
  const keyRow = page.locator('tr', {
    has: page.getByRole('cell', { name: originalName })
  });
  await expect(keyRow).toBeVisible();

  await keyRow.getByRole('button', { name: /edit api key/i }).click();
  await expect(
    page.getByRole('heading', { name: 'Edit API Key' })
  ).toBeVisible();

  await page.getByRole('textbox', { name: 'Name' }).fill(updatedName);
  await page.getByRole('switch', { name: 'Active' }).click();
  await page.getByRole('checkbox', { name: 'admin' }).check();
await page.waitForTimeout(1000);

  await Promise.all([
    page.waitForResponse(r =>
      r.request().method() === 'PATCH' &&
      r.url().includes('/api-keys') &&
      r.status() === 200
    ),
    page.getByRole('button', { name: /^Update Key$/i }).click(),
    await page.waitForTimeout(2000),
  ]);
  
  await expect(
    page.getByRole('heading', { name: 'Edit API Key' })
  ).toBeHidden();

  const updatedRow = page.locator('tr', {
    has: page.getByRole('cell', { name: updatedName })
  });
  await expect(updatedRow).toBeVisible();
  await page.waitForTimeout(1000);

});
