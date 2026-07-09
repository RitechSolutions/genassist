import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

// Minimal, node-environment Vitest setup for pure logic (no jsdom / testing-library).
// The `@` alias mirrors the app tsconfig so type-only imports resolve if ever needed.
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
