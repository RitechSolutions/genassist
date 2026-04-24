import { test as base } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

let didLoadDotEnv = false;

function loadUiTestsDotEnvOnce() {
  if (didLoadDotEnv) return;
  didLoadDotEnv = true;

  const envPath = path.resolve(__dirname, '..', '.env');
  if (!fs.existsSync(envPath)) return;

  const contents = fs.readFileSync(envPath, 'utf8');
  for (const rawLine of contents.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    const eq = line.indexOf('=');
    if (eq <= 0) continue;

    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();

    if (!key) continue;
    if (process.env[key] !== undefined) continue; // don't override externally-provided env

    process.env[key] = value;
  }
}

export const test = base.extend({
  page: async ({ page }, use) => {
    loadUiTestsDotEnvOnce();

    const seedAdminUsername = process.env.SEED_ADMIN_USERNAME ?? '';
    const seedAdminPassword = process.env.SEED_ADMIN_PASSWORD ?? '';

    if (!seedAdminUsername || !seedAdminPassword) {
      throw new Error(
        'Missing SEED_ADMIN_USERNAME / SEED_ADMIN_PASSWORD. Set them before running ui_tests.'
      );
    }

    await page.goto('/login');
    await page.waitForTimeout(2000);
    await page.getByRole('textbox', { name: 'Username or Email' }).fill(seedAdminUsername);
    await page.getByRole('textbox', { name: 'Password' }).fill(seedAdminPassword);
    await page.waitForTimeout(2000);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/dashboard');

    await use(page);
  },
});

export { expect } from '@playwright/test';
