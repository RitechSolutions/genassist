import { test, expect } from './fixtures';

test('LLM Analysts › Functionality', async ({ page }) => {
  const timestamp = Date.now();
  const analystName = `llm_analyst_${timestamp}`;
  const promptText = `Prompt generated at ${timestamp}`;
  const updatedPrompt = `Updated prompt at ${timestamp + 1}`;

  await page.getByRole('button', { name: 'Admin Tools' }).click();
  await page.getByRole('link', { name: 'LLM Analyst' }).click();
  await page.getByRole('heading', { name: 'LLM Analysts' }).click();

  await page.getByRole('button', { name: /Add New LLM Analyst/i }).click();
  await page.getByRole('textbox', { name: /name/i }).fill(analystName);
  await page.getByRole('textbox', { name: /prompt/i }).fill(promptText);
  await page.getByRole('switch', { name: /active/i }).click();
  await page.waitForTimeout(3000); 

  await page.getByRole('combobox').click();
  const options = page.locator('[role="option"]');
  await options.first().click();

  await Promise.all([
    page.waitForResponse((res) =>
      res.url().includes('/llm-analyst') && [200, 201].includes(res.status())
    ),
    page.getByRole('button', { name: /create/i }).click(),
  ]);

  const newAnalystRow = page.locator('tr', {
    has: page.locator('td', { hasText: analystName }),
  });
  await expect(newAnalystRow).toBeVisible();
  await page.getByRole('cell', { name: analystName }).click();

  await newAnalystRow.getByRole('button', { name: /edit/i }).click();
  await expect(page.getByRole('heading', { name: /edit llm analyst/i })).toBeVisible();

  const nameInput = page.getByRole('textbox', { name: /name/i });
  await expect(nameInput).toBeDisabled(); 

  await page.getByRole('textbox', { name: /prompt/i }).fill(updatedPrompt);
  await page.getByRole('switch', { name: /active/i }).click();

  await Promise.all([
    page.waitForResponse((res) =>
      res.url().includes('/llm-analyst') && res.status() === 200
    ),
    page.getByRole('button', { name: /update/i }).click(),
  ]);

  const updatedAnalystRow = page.locator('tr', {
    has: page.locator('td', { hasText: analystName }),
  });
  await expect(updatedAnalystRow).toBeVisible();
  await page.getByRole('cell', { name: updatedPrompt }).click();

  await newAnalystRow.getByRole('button', { name: /delete/i }).click();
  await page.waitForTimeout(2000); 
  await expect(page.getByText('LLM Analyst deleted')).toBeVisible();
  await page.waitForTimeout(5000);
});
