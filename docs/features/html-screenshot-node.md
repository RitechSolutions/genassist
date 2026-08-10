# HTML to Image Node

The **HTML to Image** node renders an HTML document into a PNG image inside a workflow. Give it
HTML — typed into the node or produced by an upstream node — and it returns a hosted screenshot
that downstream nodes can send, attach, or store.

## Why it matters

Workflows already generate rich HTML: an LLM node writes a formatted report, a template builds a
receipt, a scraper returns page markup. Until now there was no way to turn that HTML into a
visual artifact without an external service. This node keeps the whole flow inside GenAssist —
render a generated report card, a styled receipt, an HTML/CSS chart, or an email preview into an
image, then deliver it to a channel, attach it to a ticket, or persist it.

It reuses the platform's existing headless-browser capability (the same Chromium engine behind
the Web Scraper node), so there is no new infrastructure to run.

## How to use / enable

1. In the **AI Agents → Workflows** builder, open the node palette and, under **Tools**, drag the
   **HTML to Image** node onto the canvas.
2. Provide the HTML one of two ways:
   - **From an upstream node** — connect a node whose output is HTML (or a result containing an
     `html`/`content` field, e.g. the Web Scraper node) to the node's **input** handle.
   - **From config** — open the node and paste/template HTML into the **HTML** field. `{{variable}}`
     placeholders are resolved like other nodes.
   - If both are present, the **upstream input wins**; the config HTML is a fallback.
3. (Optional) Adjust rendering options — capture mode, viewport width/height, and an advanced
   render delay (see below).
4. Connect the node's **output** to whatever consumes the image (a channel/output node, a ticket
   node, storage, etc.). The output carries a hosted `image` URL and an `image_file_id`.
5. Save and run the workflow.

## What it does (behavior)

| Option | Effect | Default |
|--------|--------|---------|
| **HTML** | The HTML to render (config fallback; overridden by upstream input). | — |
| **Capture mode** | `Full page` captures the entire rendered height; `Viewport` captures a fixed window. | Full page |
| **Viewport width** | Render width in pixels. | 1280 |
| **Viewport height** | Fixed window height (used in Viewport mode). | 720 |
| **Wait for (ms)** *(advanced)* | Extra delay after the page settles, for late-loading assets. Capped internally. | 0 |

**Output shape:**

```json
{ "success": true, "image": "<hosted image url>", "image_file_id": "<file id>", "error": "" }
```

On any failure the node returns `{ "success": false, "image": "", "image_file_id": "", "error": "<message>" }`
rather than crashing the run, so downstream branches can react.

**Format:** PNG. **Storage:** the image is hosted through the platform's file storage (local in
dev, object storage in prod), scoped like every other node-produced file.

**Security:** external resources referenced by the HTML are fetched through the same SSRF guard as
the Web Scraper — requests that resolve to private/internal addresses are blocked. Inline `data:`
URIs are allowed. Rendering is bounded by a timeout.

## What it does not do / limitations

- **PNG only** in v1 — no JPEG/WebP selector.
- **Absolute URLs only** for external assets. Because the HTML is rendered without a page URL,
  **relative** references (`<img src="logo.png">`, relative stylesheet hrefs) have no base to
  resolve against and won't load. Use absolute `http(s)` URLs or inline/`data:` URIs.
- Does **not** render a remote URL — that's the Web Scraper node's job. This node renders supplied
  HTML.
- No PDF output, image editing/annotation, or multi-image output.

## End-to-end flow

```
Upstream HTML (or config HTML)
   → HTML to Image node
       → render in headless Chromium (page.set_content)
       → screenshot → PNG
       → host via FileManagerService
   → { image URL, image_file_id }  → downstream node
```

## Under the hood

- **Node:** `backend/app/modules/workflow/engine/nodes/html_to_image_node.py` (`HtmlToImageNode`).
- **Rendering:** `render_html_to_image()` in `backend/app/core/utils/web_scraping_utils.py` — reuses
  the module's Chromium launch and the shared `_block_private_routes` SSRF guard; uses
  `page.set_content(html)` (no navigation).
- **Hosting:** `FileManagerService`, same pattern as the Web Scraper node (path
  `html_to_image_screenshots`, `image/png`).
- **Wiring:** registered in the engine `_node_registry`, the `SUPPORTED_NODE_TYPES` allow-list, the
  dynamic-form schema dicts, and the frontend node registry / icon map.
- Chromium + OS deps are baked into the backend image (`backend/Dockerfile`,
  `playwright install --with-deps chromium`).

## Related

- Spec: `specs/006-html-screenshot-node/spec.md`
- Related: Web Scraper node (`docs/features/` sibling), `docs/features/finalize-conversation-node.md`
