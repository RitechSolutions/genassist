import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      "genassist-chat-react": path.resolve(__dirname, "../react/dist"),
      react: path.resolve(__dirname, "node_modules/react"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
    },
  },

  define: {
    'process.env': {},
    'process': {
      env: {}
    }
  },

  publicDir: false,

  build: {
    outDir: "dist",
    emptyOutDir: true,
    lib: {
      entry: "src/main.jsx",
      name: "GenassistWidget",
      fileName: "widget",
      formats: ["iife"],
    },
  },
});
