import type { Page } from '@playwright/test';
import { test, expect } from './fixtures';

const NODE_ITEMS = [
  {
    key: 'node-answer',
    label: 'Answer drafting',
    cost_usd: 0.15,
    cost_is_partial: false,
    total_tokens: 900,
    calls: 2,
    unpriced_calls: 0,
    removed: false,
  },
  {
    key: 'node-legacy',
    label: 'Legacy step',
    cost_usd: 0.04,
    cost_is_partial: false,
    total_tokens: 200,
    calls: 1,
    unpriced_calls: 0,
    removed: true,
  },
  {
    key: 'unattributed',
    label: 'Unattributed',
    cost_usd: 0.01,
    cost_is_partial: true,
    total_tokens: 50,
    calls: 1,
    unpriced_calls: 1,
  },
];

const SCOPE_NOTE = 'Workflow node calls only.';

const nodePanel = (page: Page) =>
  page.locator('div').filter({ has: page.getByRole('heading', { name: 'Cost by Node' }) }).last();

const row = (page: Page, label: string) => page.locator('li', { has: page.getByText(label, { exact: true }) });

async function stubNodeBreakdown(page: Page) {
  await page.route('**/analytics/llm-usage/breakdown*', async (route) => {
    const dimension = new URL(route.request().url()).searchParams.get('dimension');
    if (dimension !== 'node') return route.continue();
    await route.fulfill({
      json: { dimension: 'node', items: NODE_ITEMS, total: NODE_ITEMS.length },
    });
  });
}

async function openCostExplorer(page: Page) {
  await page.goto('/analytics/llm-usage');
  await expect(page.getByRole('heading', { name: 'Cost Explorer' })).toBeVisible();
}

async function selectFirstAgent(page: Page) {
  await page.getByRole('button', { name: /^Filters/ }).click();
  await page.getByRole('menuitem', { name: 'Agent' }).click();
  const submenu = page.locator('[role="menu"]').last();
  await expect(submenu.getByRole('menuitem', { name: 'All agents' })).toBeVisible();
  await submenu.getByRole('menuitem').nth(1).click();
  await page.keyboard.press('Escape');
}

test('Cost Explorer › node panel stays hidden until one agent is selected', async ({ page }) => {
  await stubNodeBreakdown(page);
  await openCostExplorer(page);

  await expect(page.getByRole('heading', { name: 'Cost by Node' })).toHaveCount(0);

  await selectFirstAgent(page);

  await expect(page.getByRole('heading', { name: 'Cost by Node' })).toBeVisible();
  await expect(page.getByText(SCOPE_NOTE)).toBeVisible();
});

test('Cost Explorer › the node panel survives a table dimension change', async ({ page }) => {
  await stubNodeBreakdown(page);
  await openCostExplorer(page);
  await selectFirstAgent(page);
  await expect(page.getByRole('heading', { name: 'Cost by Node' })).toBeVisible();

  for (const label of ['Agent', 'Usage type', 'Model']) {
    await page.getByRole('button', { name: label, exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Cost by Node' })).toBeVisible();
  }

  await expect(page.getByRole('heading', { name: 'Usage by Model' })).toBeVisible();
});

test('Cost Explorer › removed badges render only on removed nodes', async ({ page }) => {
  await stubNodeBreakdown(page);
  await openCostExplorer(page);
  await selectFirstAgent(page);

  const panel = nodePanel(page);
  await expect(panel.getByText('Legacy step')).toBeVisible();

  await expect(row(page, 'Legacy step').getByText('removed', { exact: true })).toBeVisible();
  await expect(row(page, 'Answer drafting').getByText('removed', { exact: true })).toHaveCount(0);
  await expect(row(page, 'Unattributed').getByText('removed', { exact: true })).toHaveCount(0);
});
