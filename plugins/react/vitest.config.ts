import { defineConfig } from 'vitest/config';

// Minimal, node-environment Vitest setup for pure logic (no jsdom / testing-library).
// Mirrors the main frontend app's config; tests live next to the code as `*.test.ts`.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
