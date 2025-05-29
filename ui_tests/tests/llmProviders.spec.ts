import { test, expect } from './fixtures';

test('LLM Providers › Functionality', async ({ page }) => {
  const prefix = `llm_${Date.now()}`;
  const providerName = `${prefix}_provider`;
  const updatedProviderName = `updated_${prefix}`;

  await page.getByRole('button', { name: 'Admin Tools' }).click();
  await page.getByRole('link', { name: /llm providers?/i }).click();
  await page.waitForURL('**/llm-providers');

  await page.getByRole('button', { name: /add new provider/i }).click();
  await page.getByRole('textbox', { name: /name/i }).fill(providerName);
  
  await page.getByRole('textbox', { name: 'Name' }).press('Tab');
  await page.getByRole('combobox').press('ArrowDown');
  await page.locator('button').filter({ hasText: 'Select LLM Type' }).press('ArrowDown');
  await page.getByRole('option', { name: 'OpenAI', exact: true }).click();
  await page.getByRole('textbox', { name: 'API Key' }).click();
  await page.getByRole('textbox', { name: 'API Key' }).fill('apikey');
  await page.getByRole('textbox', { name: 'API Key' }).press('Tab');
  await page.getByRole('combobox').filter({ hasText: 'GPT-3.5 Turbo' }).click();
  await page.getByRole('option', { name: 'GPT-3.5 Turbo 16K' }).click();
  await page.getByRole('switch', { name: 'Advanced' }).click();
  await page.getByRole('textbox', { name: 'Organization ID' }).click();
  await page.getByRole('textbox', { name: 'Organization ID' }).fill('organizaton id');
    await page.waitForTimeout(200); 
  await page.getByRole('button', { name: 'Create' }).click();
  await page.getByRole('button', { name: 'Edit' }).nth(1).click();
    await page.waitForTimeout(3000); 
  await page.getByRole('textbox', { name: 'Name' }).click();
  await page.getByRole('textbox', { name: 'Name' }).fill('Provider Name Updated');
  const ollamaComboBox = page.getByRole('combobox').filter({ hasText: 'ollama' });
  if (await ollamaComboBox.count() > 0) {
    await ollamaComboBox.click();
  }
    await page.getByRole('combobox').filter({ hasText: 'OpenAI' }).click();
  await page.getByRole('option', { name: 'Llama', exact: true }).click();
  await page.getByRole('textbox', { name: 'Base URL' }).click();
  await page.getByRole('textbox', { name: 'Base URL' }).fill('http://localhost:8000');
  await page.getByRole('combobox').filter({ hasText: 'Select Model' }).click();
  await page.getByRole('option', { name: 'Llama 2 7B Chat' }).click();
  await page.getByRole('switch', { name: 'Advanced' }).click();
  await page.getByRole('textbox', { name: 'API Key' }).click();
  await page.getByRole('textbox', { name: 'API Key' }).fill('api key');
  await page.getByRole('textbox', { name: 'Stop Sequences' }).click();
  await page.getByRole('textbox', { name: 'Stop Sequences' }).fill('Human');
    await page.waitForTimeout(1000); 
  await page.getByRole('button', { name: 'Update' }).click();
    await page.waitForTimeout(3000); 
  await page.getByRole('button', { name: 'Delete' }).nth(1).click();
  await page.waitForTimeout(3000);
});
