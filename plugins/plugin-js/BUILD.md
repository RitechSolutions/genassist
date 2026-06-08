# Building `widget.iife.js` and `widget.css`

Technical guide for producing the standalone GenAssist embed artifacts from `plugins/plugin-js`.

## Artifacts

| Output | Path | Role |
|--------|------|------|
| JavaScript bundle | `dist/widget.iife.js` | Self-contained IIFE: React, ReactDOM, `GenAgentChat`, and bootstrap logic |
| Stylesheet | `dist/widget.css` | Extracted CSS from the widget entry (`font.css`, `index.css`), with font binaries inlined |

Both files are required on the host page. The chat UI itself uses mostly inline styles inside the JS bundle; `widget.css` mainly carries reset rules and bundled `@font-face` data.

`dist/` is generated and gitignored. Do not edit files under `dist/` by hand—always rebuild.

---

## Prerequisites

- **Node.js 16+** and **npm**
- Repository checkout with `plugins/react` present (the widget bundles `GenAgentChat` from that package)
- GenAssist API credentials for runtime testing (`baseUrl`, `apiKey`, optional `tenant`)

---

## One-time setup

From the monorepo root:

```bash
cd plugins/plugin-js
npm install
```

### Font stylesheet (required for a successful build)

`src/font.css` is **not** committed (see `.gitignore`). Create it before the first build:

```bash
cp src/font.example.css src/font.css
```

Uncomment or replace the `@font-face` blocks in `src/font.css`, and place matching font files under `src/fonts/` (also gitignored except `README.txt`). Paths in `url(...)` must be relative to `src/font.css`, e.g. `url("./fonts/Roboto/static/Roboto-Regular.ttf")`.

If you do not need bundled fonts, use an empty `src/font.css` (or only comments) to keep `widget.css` small, and load fonts from the host page instead.

### Optional: rebuild the React library

The widget entry imports the chat component from source:

```text
src/main.jsx  →  import { GenAgentChat } from "../../react/src"
```

You do **not** need `npm run build` in `plugins/react` for the widget build to succeed. Rebuild `plugins/react` only if you are publishing or consuming `genassist-chat-react` as a separate package.

---

## Generate the artifacts

```bash
cd plugins/plugin-js
npm run build
```

This runs `vite build` (see `package.json`). On success you should see output similar to:

```text
dist/widget.css       … kB │ gzip: … kB
dist/widget.iife.js   … kB │ gzip: … kB
✓ built in …s
```

Verify the files exist:

```bash
ls -la dist/widget.iife.js dist/widget.css
```

### What the build does

Vite is configured in **library mode** with a single IIFE output:

```js
// vite.config.js (excerpt)
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
```

Effects:

1. **`widget.iife.js`** — Rollup bundles `src/main.jsx`, all JS/TSX reachable from it (including `plugins/react/src`), React, and ReactDOM into one immediately-invoked function. The global name `GenassistWidget` is registered by the IIFE wrapper; the host page typically only needs the script tag and `window.GenassistBootstrap` (defined in `main.jsx`).
2. **`widget.css`** — Vite extracts CSS imported from the entry graph. The entry pulls styles here:

   ```js
   // src/main.jsx
   import "./font.css";
   import "./index.css";
   ```

   Any `url(...)` font references in `font.css` are resolved at build time and, by default, **inlined as `data:` URLs** inside `widget.css`, so production hosts do not need separate font file requests.

3. **`publicDir: false`** — Nothing from a `public/` folder is copied; output is only the lib bundle and extracted CSS.
4. **`emptyOutDir: true`** — Each build replaces the previous `dist/` contents.

Aliases in `vite.config.js` pin `react` / `react-dom` to this package’s `node_modules` and map `genassist-chat-react` to `plugins/react/dist` for tooling; the entry still resolves the component from `plugins/react/src` via the relative import in `main.jsx`.

---

## CSS vs JavaScript styling

| Source | Ends up in |
|--------|------------|
| `src/font.css`, `src/index.css` | `widget.css` |
| `GenAgentChat` inline styles and `<style>` keyframes in `plugins/react/src` | `widget.iife.js` |

`src/index.css` applies a minimal reset on `#genassist-chat-root` and descendants. Theme colors and typography are driven by `window.GENASSIST_CONFIG.theme` at runtime, not by extra CSS files in `dist/`.

---

## Local preview after build

**Option A — serve script (build + copy + HTTP server):**

```bash
npm run serve
```

This runs `vite build`, copies `dist/` to `example-widget/dist/`, and serves `example-widget/` on **http://localhost:8022**. Open `http://localhost:8022/index.html`.

**Option B — build only, then copy manually:**

```bash
npm run build
rm -rf example-widget/dist && cp -r dist example-widget/
cd example-widget && python3 -m http.server 8022
```

Configure credentials in `example-widget/index.html` or via `example-widget/config/config.js` (copy from `config.example.js`).

---

## Ship to production

1. Run `npm run build` in `plugins/plugin-js`.
2. Upload **`dist/widget.iife.js`** and **`dist/widget.css`** to your CDN or static host (same origin or CORS-friendly).
3. On each page, before or with the script:
   - Set `window.GENASSIST_CONFIG` (see [README.md](./README.md#configuration)).
   - Provide `<div id="genassist-chat-root"></div>`.
   - Load CSS, then JS:

```html
<div id="genassist-chat-root"></div>
<script>
  window.GENASSIST_CONFIG = { baseUrl: '…', apiKey: '…' /* … */ };
</script>
<link rel="stylesheet" href="https://your-cdn.example/widget.css">
<script src="https://your-cdn.example/widget.iife.js"></script>
```

Load order: config → root element → **stylesheet** → **script**. After changing config at runtime, call `window.GenassistBootstrap()`.

---

## Customizing bundle size

| Goal | Action |
|------|--------|
| Smaller `widget.css` | Remove or trim `@font-face` in `src/font.css`; use host-page `<link>` fonts |
| Different typeface | Edit `src/font.css` + `src/fonts/`, set `theme.fontFamily` in config, rebuild |
| Smaller `widget.iife.js` | Not configurable in this package alone; depends on `plugins/react` tree-shaking and dependencies |

Expect `widget.css` to be large when multiple font weights are embedded as base64.

---

## npm scripts reference

| Script | Command | Purpose |
|--------|---------|---------|
| `build` | `vite build` | **Produces `dist/widget.iife.js` and `dist/widget.css`** |
| `dev` | `vite` | Dev server for `index.html` (not the IIFE dist layout) |
| `serve` | `vite build && bash serve.sh` | Build, copy to `example-widget/dist`, serve on port 8022 |
| `preview` | `vite preview` | Preview Vite app output (not the primary widget workflow) |

---

## Troubleshooting

### Build fails: cannot resolve `./font.css`

Create `src/font.css` from `src/font.example.css` (see [One-time setup](#font-stylesheet-required-for-a-successful-build)).

### Build fails: cannot resolve font `url(...)` in `font.css`

Ensure files exist under `src/fonts/` at the paths referenced in `src/font.css`.

### `dist/` is empty or stale

Run `npm run build` from `plugins/plugin-js`, not the repo root. Check the terminal for Rollup/Vite errors.

### Widget loads but looks unstyled / wrong font

Confirm `widget.css` is linked and returns 200. Confirm `theme.fontFamily` matches the `font-family` in your `@font-face` rules.

### Example page 404 on `./dist/widget.*`

Run `npm run build` and either `npm run serve` or copy `dist/` into `example-widget/dist/`.

### Huge `widget.css`

Usually embedded fonts. Reduce faces in `src/font.css` or switch to external font hosting.

---

## Related docs

- [README.md](./README.md) — integration, configuration, runtime behavior
- [example-widget/README.md](./example-widget/README.md) — help-center style embedding
- [src/fonts/README.txt](./src/fonts/README.txt) — font file layout and licensing notes
