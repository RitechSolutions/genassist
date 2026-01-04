import { test, expect } from './fixtures';

test('App Settings › Create & Edit Flow', async ({ page }) => {
  const suffix = Date.now();
  const settingKey = `setting_${suffix}`;
  const settingValue = `value_${suffix}`;
  const newValue = `updated_${suffix}`;
  const description = `A test setting created at ${suffix}`;

  await page.getByRole('button', { name: 'Admin Tools' }).click();
  await page.getByRole("link", { name: /App Settings?/i }).click();
  await page.waitForURL("**/app-settings");
    await page.waitForTimeout(1000);
  await expect(page.getByRole('heading', { name: 'App Settings' })).toBeVisible();

  await page.getByRole('button', { name: 'Add New Setting' }).click();
  await expect(page.getByRole('heading', { name: 'Add New Setting' })).toBeVisible();

  await page.getByLabel('Setting Key').fill(settingKey);
  await page.getByLabel('Value').fill(settingValue);
  await page.getByLabel('Description').fill(description);
  // Toggle “Encrypted” on
  await page.getByLabel('Encrypted').click();

const [postResponse] = await Promise.all([
  page.waitForResponse(r =>
    r.request().method() === 'POST' &&
    r.url().includes('/app-settings') &&
    [200, 201].includes(r.status())
  ),
  page.getByRole('button', { name: 'Create Setting' }).click(),
]);

const created = await postResponse.json();
const createdId = created.id;

  await expect(page.getByRole('heading', { name: 'Add New Setting' })).toBeHidden();

  const row = page.locator('tr', {
    has: page.locator('td', { hasText: settingKey }),
  }).filter({
    has: page.locator('td', { hasText: '••••••••' }) // because encrypted
  });
  await expect(row).toBeVisible();

  await row.getByRole('button', { name: 'Edit Setting' }).click();
  await expect(page.getByRole('heading', { name: 'Edit Setting' })).toBeVisible();

  const valueInput = page.getByLabel('Value');
  await valueInput.fill(newValue);
  await page.getByLabel('Encrypted').click(); // turn off

await Promise.all([
  page.waitForResponse(r =>
    r.request().method() === 'PATCH' &&
    r.url().endsWith(`/app-settings/${createdId}`) &&
    r.status() === 200
  ),
  page.waitForResponse(r =>
    r.request().method() === 'GET' &&
    r.url().includes('/app-settings') &&
    r.status() === 200
  ),
  page.getByRole('button', { name: 'Update Setting' }).click(),
]);

await expect(page.getByRole('heading', { name: 'Edit Setting' })).toBeHidden();

  const updatedRow = page.locator('tr', {
    has: page.locator('td', { hasText: settingKey }),
  }).filter({
    has: page.locator('td', { hasText: newValue })
  });
  await expect(updatedRow).toBeVisible();

  await expect(page.getByText('Setting updated successfully')).toBeVisible();

  await updatedRow.getByRole('button', { name: 'Delete Setting' }).click();
  await Promise.all([
    page.waitForResponse(r =>
      r.request().method() === 'DELETE' &&
      r.url().endsWith(`/app-settings/${createdId}`) &&
      [200, 204].includes(r.status())
    ),
    page.waitForResponse(r =>
      r.request().method() === 'GET' &&
      r.url().includes('/app-settings') &&
      r.status() === 200
    ),
    page.getByRole('button', { name: 'Delete' }).click(),
  ]);

  await expect(updatedRow).toBeHidden();
  await expect(page.getByText('Setting deleted successfully')).toBeVisible();

  await page.waitForTimeout(1000);
});
