import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
  resolve: {
    alias: {
      '../../dist': path.resolve(__dirname, '../dist'),
      '../../src': path.resolve(__dirname, '../src')
    }
  },
  build: {
    sourcemap: true,
  },
  esbuild: {
    sourcemap: true,
  },
  optimizeDeps: {
    include: ['../../src/**/*']
  }
}); 