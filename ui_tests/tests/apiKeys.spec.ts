import { test, expect } from './fixtures';
import type { Page, Route } from '@playwright/test';

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
    await page.waitForTimeout(1000); 
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

// The tests below serve the list from an in-memory store so a tenant with more
// keys than one page fits can be set up deterministically

type StoredKey = {
  id: string;
  name: string;
  is_active: number;
  user_id: string;
  roles: [];
  created_at: string;
};

const BASE_MS = Date.UTC(2026, 0, 1, 12, 0);

const makeKey = (id: string, name: string, ageMinutes: number): StoredKey => ({
  id,
  name,
  is_active: 1,
  user_id: 'mock-user',
  roles: [],
  created_at: new Date(BASE_MS - ageMinutes * 60_000).toISOString(),
});

const seedStore = (count: number): StoredKey[] =>
  Array.from({ length: count }, (_, i) => makeKey(`mock-${i}`, `zz_mock_${String(i).padStart(2, '0')}`, i));

type ListHook = (url: URL, route: Route) => Promise<boolean> | boolean;


async function mockApiKeys(page: Page, store: StoredKey[], onList?: ListHook): Promise<URL[]> {
  const listUrls: URL[] = [];

  await page.route('**/api-keys**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (method === 'GET' && url.pathname.endsWith('/api-keys/list')) {
      listUrls.push(url);
      if (onList && (await onList(url, route))) return;

      const skip = Number(url.searchParams.get('skip') ?? '0');
      const limit = Number(url.searchParams.get('limit') ?? '20');
      const search = (url.searchParams.get('search') ?? '').toLowerCase();
      const matched = search ? store.filter((key) => key.name.toLowerCase().includes(search)) : store;

      return route.fulfill({
        json: {
          items: matched.slice(skip, skip + limit),
          total: matched.length,
          page: Math.floor(skip / limit) + 1,
          page_size: limit,
          total_pages: Math.ceil(matched.length / limit),
        },
      });
    }

    if (method === 'POST' && url.pathname.endsWith('/api-keys')) {
      const body = request.postDataJSON() as { name: string };
      const created = makeKey(`mock-new-${store.length}`, body.name, -1);
      store.unshift(created);
      return route.fulfill({ json: { ...created, key_val: 'mock-secret-value' } });
    }

    if (method === 'PATCH' && /\/api-keys\/[^/]+$/.test(url.pathname)) {
      const id = url.pathname.split('/').pop();
      const body = request.postDataJSON() as { name?: string };
      const row = store.find((key) => key.id === id);
      if (!row) return route.fulfill({ status: 404, json: { detail: 'not found' } });
      if (typeof body.name === 'string') row.name = body.name;
      return route.fulfill({ json: row });
    }

    return route.fallback();
  });

  return listUrls;
}

async function openApiKeys(page: Page) {
  await page.getByRole('button', { name: 'Admin Tools' }).click();
  await page.getByRole('link', { name: /api keys/i }).click();
  await page.waitForURL('**/api-keys');
}

const pageLink = (page: Page, number: string) => page.getByRole('link', { name: number, exact: true });

test('API Keys › every key is reachable when there are more than one page of them', async ({ page }) => {
  const store = seedStore(21);
  const listUrls = await mockApiKeys(page, store);

  await openApiKeys(page);

  await expect(page.getByText('Showing 1 to 10 of 21 results')).toBeVisible();
  expect(listUrls[0].searchParams.get('skip')).toBe('0');
  expect(listUrls[0].searchParams.get('limit')).toBe('10');

  await pageLink(page, '2').click();
  await expect(page.getByText('Showing 11 to 20 of 21 results')).toBeVisible();
  expect(listUrls[listUrls.length - 1].searchParams.get('skip')).toBe('10');

  await pageLink(page, '3').click();
  await expect(page.getByText('Showing 21 to 21 of 21 results')).toBeVisible();
  await expect(page.getByRole('cell', { name: 'zz_mock_20' })).toBeVisible();
});

test('API Keys › a key created from a later page lands on top of page 1', async ({ page }) => {
  const store = seedStore(21);
  const listUrls = await mockApiKeys(page, store);
  const createdName = 'zz_mock_created';

  await openApiKeys(page);
  await pageLink(page, '2').click();
  await expect(page.getByText('Showing 11 to 20 of 21 results')).toBeVisible();

  await page.getByRole('button', { name: /generate new api key/i }).click();
  await page.getByRole('textbox', { name: /name/i }).fill(createdName);
  await Promise.all([
    page.waitForResponse(
      (response) => response.request().method() === 'POST' && response.url().includes('/api-keys')
    ),
    page.getByRole('button', { name: /^Generate Key$/i }).click(),
  ]);
  await page.getByRole('button', { name: 'Cancel' }).click();

  await expect(page.getByText('Showing 1 to 10 of 22 results')).toBeVisible();
  await expect(page.getByRole('cell', { name: createdName })).toBeVisible();
  expect(listUrls[listUrls.length - 1].searchParams.get('skip')).toBe('0');
});

test('API Keys › a page past the end falls back to the last page that has rows', async ({ page }) => {
  const store = seedStore(21);
  const listUrls = await mockApiKeys(page, store);

  await openApiKeys(page);
  await pageLink(page, '2').click();
  await expect(page.getByText('Showing 11 to 20 of 21 results')).toBeVisible();

  store.splice(15);

  await pageLink(page, '3').click();
  await expect(page.getByText('Showing 11 to 15 of 15 results')).toBeVisible();

  const skips = listUrls.map((url) => url.searchParams.get('skip'));
  expect(skips.slice(-2)).toEqual(['20', '10']);
});

test('API Keys › a failed list offers a retry that recovers', async ({ page }) => {
  const store = seedStore(12);
  let failNext = true;
  await mockApiKeys(page, store, async (_url, route) => {
    if (!failNext) return false;
    failNext = false;
    await route.fulfill({ status: 500, json: { detail: 'boom' } });
    return true;
  });

  await openApiKeys(page);

  const retry = page.getByRole('button', { name: 'Try again' });
  await expect(retry).toBeVisible();
  await retry.click();

  await expect(page.getByText('Showing 1 to 10 of 12 results')).toBeVisible();
  await expect(page.getByRole('cell', { name: 'zz_mock_00' })).toBeVisible();
});

test('API Keys › a slow search response cannot overwrite a newer one', async ({ page }) => {
  const store = [
    ...Array.from({ length: 4 }, (_, i) => makeKey(`ab-${i}`, `zz_ab_${i}`, i)),
    ...Array.from({ length: 6 }, (_, i) => makeKey(`alpha-${i}`, `zz_alpha_${i}`, 10 + i)),
  ];

  let release = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await mockApiKeys(page, store, async (url) => {
    if (url.searchParams.get('search') === 'a') await held;
    return false;
  });

  await openApiKeys(page);
  await expect(page.getByText('Showing 1 to 10 of 10 results')).toBeVisible();

  const search = page.getByPlaceholder('Search API keys...');
  const searchTerm = (url: string) => new URL(url).searchParams.get('search');

  const requestA = page.waitForRequest((request) => searchTerm(request.url()) === 'a');
  await search.fill('a');
  await requestA;

  const responseB = page.waitForResponse((response) => searchTerm(response.url()) === 'ab');
  await search.fill('ab');
  await responseB;

  await expect(page.getByText('Showing 1 to 4 of 4 results')).toBeVisible();

  const responseA = page.waitForResponse((response) => searchTerm(response.url()) === 'a');
  release();
  await responseA;

  await page.evaluate(
    () => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
  );

  await expect(page.getByText('Showing 1 to 4 of 4 results')).toBeVisible();
  await expect(page.getByRole('cell', { name: 'zz_alpha_0' })).toHaveCount(0);
});
