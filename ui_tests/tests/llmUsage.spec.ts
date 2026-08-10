import type { Page, Route } from '@playwright/test';
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

const SOURCE_ITEMS = [
  {
    key: 'workflow',
    label: 'Workflows',
    cost_usd: 1.2,
    cost_is_partial: false,
    total_tokens: 8000,
    calls: 40,
    unpriced_calls: 0,
  },
  {
    key: 'evaluation',
    label: 'Evaluations',
    cost_usd: 0.3,
    cost_is_partial: false,
    total_tokens: 1500,
    calls: 6,
    unpriced_calls: 0,
  },
];

const METHOD_ITEMS = [
  {
    key: 'llm_judge',
    label: 'LLM Judge',
    cost_usd: 0.2,
    cost_is_partial: false,
    total_tokens: 1000,
    calls: 4,
    unpriced_calls: 0,
  },
  {
    key: 'provenance_judge',
    label: 'Provenance',
    cost_usd: 0.1,
    cost_is_partial: false,
    total_tokens: 500,
    calls: 2,
    unpriced_calls: 0,
  },
];

const SCOPE_NOTE = 'Workflow node calls only.';

const row = (page: Page, label: string) => page.locator('li', { has: page.getByText(label, { exact: true }) });

const methodRow = (page: Page, label: string) =>
  page.locator('tr', { has: page.getByText(label, { exact: true }) });

const evaluationsToggle = (page: Page) => page.getByRole('button', { name: /^Evaluations/ });

const evaluationStatusCell = (page: Page) => page.locator('td.pl-10');

type BreakdownStub = (route: Route) => Promise<unknown>;

async function stubBreakdowns(page: Page, stubs: Record<string, BreakdownStub>): Promise<string[]> {
  const requested: string[] = [];
  await page.route('**/analytics/llm-usage/breakdown*', async (route) => {
    const dimension = new URL(route.request().url()).searchParams.get('dimension') ?? '';
    requested.push(dimension);
    const stub = stubs[dimension];
    if (!stub) return route.continue();
    await stub(route);
  });
  return requested;
}

const serve =
  (dimension: string, items: unknown[]): BreakdownStub =>
  (route) =>
    route.fulfill({ json: { dimension, items, total: items.length } });

const stubNodeBreakdown = (page: Page) => stubBreakdowns(page, { node: serve('node', NODE_ITEMS) });

async function openCostExplorer(page: Page) {
  const analytics = page.getByRole('button', { name: 'Analytics' });
  if ((await analytics.getAttribute('aria-expanded')) !== 'true') await analytics.click();
  await page.getByRole('link', { name: 'Cost Explorer' }).click();
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

async function showUsageTypes(page: Page) {
  await page.getByRole('button', { name: 'Usage type', exact: true }).click();
  await expect(evaluationsToggle(page)).toBeVisible();
}

async function expandEvaluations(page: Page) {
  await evaluationsToggle(page).click();
  await expect(evaluationsToggle(page)).toHaveAttribute('aria-expanded', 'true');
}

test('Cost Explorer › node panel stays hidden until one agent is selected', async ({ page }) => {
  await stubNodeBreakdown(page);
  await openCostExplorer(page);

  await expect(page.getByRole('heading', { name: 'Cost by Node' })).toHaveCount(0);

  await selectFirstAgent(page);

  await expect(page.getByRole('heading', { name: 'Cost by Node' })).toBeVisible();
  await expect(page.getByText(SCOPE_NOTE)).toBeVisible();
});

test('Cost Explorer › the node breakdown is requested only after an agent is selected', async ({ page }) => {
  const requested = await stubNodeBreakdown(page);
  await openCostExplorer(page);

  await expect.poll(() => requested).toContain('provider');
  expect(requested).not.toContain('node');

  await selectFirstAgent(page);

  await expect(page.getByRole('heading', { name: 'Cost by Node' })).toBeVisible();
  await expect.poll(() => requested).toContain('node');
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

  await expect(row(page, 'Legacy step')).toBeVisible();

  await expect(row(page, 'Legacy step').getByText('removed', { exact: true })).toBeVisible();
  await expect(row(page, 'Answer drafting').getByText('removed', { exact: true })).toHaveCount(0);
  await expect(row(page, 'Unattributed').getByText('removed', { exact: true })).toHaveCount(0);
});

test('Cost Explorer › evaluation methods are requested only once the row is expanded', async ({ page }) => {
  const requested = await stubBreakdowns(page, {
    source: serve('source', SOURCE_ITEMS),
    evaluation_method: serve('evaluation_method', METHOD_ITEMS),
  });
  await openCostExplorer(page);
  await showUsageTypes(page);

  expect(requested).not.toContain('evaluation_method');

  await expandEvaluations(page);

  await expect.poll(() => requested).toContain('evaluation_method');
});

test('Cost Explorer › an in-flight evaluation breakdown holds the row on a placeholder', async ({ page }) => {
  let release = () => {};
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await stubBreakdowns(page, {
    source: serve('source', SOURCE_ITEMS),
    evaluation_method: async (route) => {
      await pending;
      await serve('evaluation_method', METHOD_ITEMS)(route);
    },
  });
  await openCostExplorer(page);
  await showUsageTypes(page);
  await expandEvaluations(page);

  await expect(evaluationStatusCell(page).locator('.animate-pulse')).toBeVisible();
  await expect(page.getByText('LLM Judge')).toHaveCount(0);

  release();

  await expect(page.getByText('LLM Judge')).toBeVisible();
});

test('Cost Explorer › a failed evaluation breakdown reports itself in the row', async ({ page }) => {
  await stubBreakdowns(page, {
    source: serve('source', SOURCE_ITEMS),
    evaluation_method: (route) => route.fulfill({ status: 500, json: { detail: 'breakdown unavailable' } }),
  });
  await openCostExplorer(page);
  await showUsageTypes(page);
  await expandEvaluations(page);

  await expect(page.getByText('Failed to load evaluation breakdown.')).toBeVisible();
  await expect(evaluationsToggle(page).getByText('methods')).toHaveCount(0);
});

test('Cost Explorer › an evaluation breakdown with no spend says so', async ({ page }) => {
  await stubBreakdowns(page, {
    source: serve('source', SOURCE_ITEMS),
    evaluation_method: serve('evaluation_method', []),
  });
  await openCostExplorer(page);
  await showUsageTypes(page);
  await expandEvaluations(page);

  await expect(page.getByText('No evaluation LLM spend in this period.')).toBeVisible();
});

test('Cost Explorer › a settled evaluation breakdown lists each method with its cost', async ({ page }) => {
  await stubBreakdowns(page, {
    source: serve('source', SOURCE_ITEMS),
    evaluation_method: serve('evaluation_method', METHOD_ITEMS),
  });
  await openCostExplorer(page);
  await showUsageTypes(page);
  await expandEvaluations(page);

  await expect(evaluationsToggle(page).getByText('2 methods')).toBeVisible();
  await expect(methodRow(page, 'LLM Judge').getByText('$0.2000')).toBeVisible();
  await expect(methodRow(page, 'Provenance').getByText('$0.1000')).toBeVisible();
});
