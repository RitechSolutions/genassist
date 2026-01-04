# Playwright Test Documentation

## Recording Tests

To record a new test with Playwright:

1. Open your terminal in the project root directory
2. Run the following command to start the test recorder:
   ```bash
   npx playwright codegen <URL>
   ```
   Replace `<URL>` with the website URL you want to test (e.g., http://localhost:3000)

3. The Playwright Inspector will open along with a browser window
4. Interact with your website as you normally would
5. The recorder will generate test code based on your actions
6. Copy the generated code to your test file in the `tests` directory

## Running Tests

### Running All Tests

To run all tests:
```bash
npx playwright test
```

### Running Tests in UI Mode

To run tests with the UI mode:
```bash
npx playwright test --ui
```

### Running a Specific Test File

To run tests from a specific file:
```bash
npx playwright test tests/yourtest.spec.ts
```

### Running Tests in Different Browsers

Tests will run in all configured browsers (Chromium, Firefox, and WebKit) by default. To run in a specific browser:
```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

### Viewing Test Reports

After running tests, you can view the HTML report:
```bash
npx playwright show-report
```

## Debug Tests

To debug tests:
1. Add the `--debug` flag when running tests:
   ```bash
   npx playwright test --debug
   ```
2. Use `await page.pause()` in your test code to pause execution at specific points

## Test Configuration

The test configuration is in `playwright.config.ts`. This includes:
- Browser configurations
- Test directory settings
- Parallel execution settings
- Reporter settings

For more detailed information, visit the [Playwright documentation](https://playwright.dev/docs/intro).