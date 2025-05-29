import { test, expect } from './fixtures';

test.describe('Data Sources › Functionality', () => {
  test('create, edit and delete a data source', async ({ page }) => {
    const timestamp = Date.now();
    const name = `s3 connection ${timestamp}`;

    const updatedName = `s3 updated ${timestamp}`;
    const updatedType = `S3-updated`;

    await page.getByRole('button', { name: 'Admin Tools' }).click();
    await page.getByRole('link', { name: 'Data Sources' }).click();

    await page.getByRole('button', { name: /add new data source/i }).click();

      await page.getByRole('textbox', { name: 'Name', exact: true }).fill(name);
  await page.getByRole('combobox').click();
  await page.getByRole('option', { name: 'S3' }).click();
  await page.getByRole('textbox', { name: 'Access key' }).click();
  const access_key = "AKIAXXX";
  await page.getByRole('textbox', { name: 'Access key' }).fill(access_key);
  await page.getByRole('textbox', { name: 'Secret key' }).click();
  await page.getByRole('textbox', { name: 'Secret key' }).fill('secret');
  await page.getByRole('textbox', { name: 'Region' }).click();
  await page.getByRole('textbox', { name: 'Region' }).fill('US');
  await page.getByRole('textbox', { name: 'Bucket name' }).click();
  await page.getByRole('textbox', { name: 'Bucket name' }).fill('bucket');
  await page.getByRole('textbox', { name: 'Prefix' }).click();
  await page.getByRole('textbox', { name: 'Prefix' }).fill('383');
  await page.getByRole('button', { name: 'Create' }).click();

    await page.waitForTimeout(1000);

    await expect(
      page.getByRole('heading', { name: 'Create Data Source' })
    ).toBeHidden();
    await page.waitForTimeout(1000);

    const row = page.locator('tr', { hasText: name });
    await expect(row).toBeVisible();

    await page.waitForTimeout(2000);

    await row.locator('button[title="Edit Data Source"]').click();
    await expect(
      page.getByRole('heading', { name: 'Edit Data Source' })
    ).toBeVisible();

    await page.getByLabel('Name').fill(updatedName);

      await page.getByRole('combobox').click();
  await page.getByRole('option', { name: 'Database' }).click();
  await page.getByRole('textbox', { name: 'Database host' }).click();
  await page.getByRole('textbox', { name: 'Database host' }).fill('database host');
  await page.getByPlaceholder('Database port').click();
  await page.getByPlaceholder('Database port').fill('2015');
  await page.getByRole('textbox', { name: 'Database name' }).click();
  await page.getByRole('textbox', { name: 'Database name' }).fill('data source');
  await page.getByRole('textbox', { name: 'Database user' }).click();
  await page.getByRole('textbox', { name: 'Database user' }).fill('root');
  await page.getByRole('textbox', { name: 'Database user' }).press('Tab');
  await page.getByRole('textbox', { name: 'Database password' }).fill('password');
    await page.getByRole('switch', { name: 'Advanced', exact: true }).click();

  await page.getByRole('textbox', { name: 'SSH tunnel host' }).click();
  await page.getByRole('textbox', { name: 'SSH tunnel host' }).fill('ssh:host');
  await page.getByPlaceholder('SSH tunnel port').click();
  await page.getByPlaceholder('SSH tunnel port').fill('2122');
  await page.getByRole('textbox', { name: 'SSH tunnel user' }).click();
  await page.getByRole('textbox', { name: 'SSH tunnel user' }).fill('user');
  await page.getByRole('textbox', { name: 'SSH tunnel private key' }).click();
  await page.getByRole('textbox', { name: 'SSH tunnel private key' }).fill('private_key');
  await page.getByRole('button', { name: 'Update' }).click();

    await page.waitForTimeout(1000);

    await expect(
      page.getByRole('heading', { name: 'Edit Data Source' })
    ).toBeHidden();

    const updatedRow = page.locator('tr', { hasText: updatedName });
    const updatedTypeRow = page.locator('tr', { hasText: updatedType });

    await expect(updatedRow).toBeVisible();

    await page.waitForTimeout(1000);

    await updatedRow.locator('button[title="Delete Data Source"]').click();
    await page.waitForTimeout(1000);
    await expect(
      page.getByText('Data source deleted')
    ).toBeVisible({ timeout: 6000 });

    await expect(updatedRow).not.toBeVisible();
    await expect(updatedTypeRow).not.toBeVisible();
  });
});
