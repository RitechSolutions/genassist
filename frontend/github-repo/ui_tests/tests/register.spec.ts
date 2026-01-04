import { test, expect } from './fixtures';

test('Register', async ({ page }) => {
  await page.goto('/register');
  await page.getByRole('textbox', { name: 'Enter your username' }).click();
  await page.getByRole('textbox', { name: 'Enter your username' }).fill('user@gmail.com');
  await page.getByRole('textbox', { name: 'Enter your username' }).press('Tab');
  await page.getByRole('textbox', { name: 'Enter your password' }).fill('User123.');
  await page.getByRole('textbox', { name: 'Enter your password' }).press('Tab');
  await page.getByRole('textbox', { name: 'Confirm your password' }).fill('User123.');
  await page.getByRole('button', { name: 'Sign Up' }).click();
});