import { test, expect } from './fixtures';

test('LLM Providers › Functionality', async ({ page }) => {
  const prefix = `llm_${Date.now()}`;
  const providerName = `${prefix}_provider`;
  const updatedProviderName = `updated_${prefix}`;

  await test.step('Navigate to LLM Providers page', async () => {
    await page.getByRole('button', { name: 'Admin Tools' }).click();
    await page.getByRole('link', { name: /llm providers?/i }).click();
    await expect(page).toHaveURL(/.*llm-providers/);
  });

  await test.step('Create a new LLM provider', async () => {
    await page.getByRole('button', { name: /add new provider/i }).click();
    await page.getByRole('textbox', { name: /name/i }).fill(providerName);
    
    await page.getByRole('combobox').press('ArrowDown');
    await page.getByRole('option', { name: 'OpenAI', exact: true }).click();

    await page.getByRole('textbox', { name: 'API Key' }).fill('apikey');
    await page.getByRole('combobox').filter({ hasText: 'GPT-3.5 Turbo' }).click();
    await page.getByRole('option', { name: 'GPT-3.5 Turbo 16K' }).click();

    await page.getByRole('switch', { name: 'Advanced' }).click();
    await page.getByRole('textbox', { name: 'Organization ID' }).fill('organization id');

    await page.getByRole('button', { name: 'Create' }).click();
  });

  await test.step('Edit the created provider', async () => {
    await page.getByRole('button', { name: 'Edit' }).nth(1).click();

    const nameInput = page.getByRole('textbox', { name: 'Name' });
    await expect(nameInput).toBeVisible();
    await nameInput.fill(updatedProviderName);

    const ollamaComboBox = page.getByRole('combobox').filter({ hasText: 'ollama' });
    const openAIComboBox = page.getByRole('combobox').filter({ hasText: 'OpenAI' });
    const llamaComboBox = page.getByRole('combobox').filter({ hasText: /^Llama$/ });

    if (await ollamaComboBox.count() > 0) {
      await ollamaComboBox.click();
      await page.getByRole('option', { name: 'Llama', exact: true }).click();
    } else if (await openAIComboBox.count() > 0) {
      await openAIComboBox.click();
    } else if (await llamaComboBox.count() > 0) {
      await llamaComboBox.click();
    }
    await page.getByRole('option', { name: 'Llama', exact: true }).click();
    await page.getByRole('textbox', { name: 'Base URL' }).fill('http://localhost:8000');

    const selectModelComboBox = page.getByRole('combobox').filter({ hasText: 'Select Model' });
    if (await selectModelComboBox.count() > 0) {
      await selectModelComboBox.click();
    } else {
      const llama27BOption = page.getByRole('option', { name: 'Llama 2 7B Chat' });
      if (await llama27BOption.count() > 0) {
        await llama27BOption.click();
      }
    }

    await page.getByRole('switch', { name: 'Advanced' }).click();
    await page.getByRole('textbox', { name: 'API Key' }).fill('api key');
    await page.getByRole('textbox', { name: 'Stop Sequences' }).fill('Human');

    await page.getByRole('button', { name: 'Update' }).click();
  });

await test.step('Delete the provider', async () => {
  const row = page.locator('tr', { hasText: updatedProviderName });

  await row.getByRole('button', { name: /delete/i }).click();

  const confirmDeleteButton = page.getByRole('button', { name: /^Delete$/ });
  await expect(confirmDeleteButton).toBeVisible();
  await confirmDeleteButton.click();

  await expect(page.getByText('LLM Provider deleted')).toBeVisible();
  await page.waitForTimeout(2000);
});
});
