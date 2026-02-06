# Genassist Widget Plugin (JavaScript)

A React-based widget plugin for integrating Genassist chat into any website using a standalone JavaScript bundle.

## Overview

This project builds a standalone JavaScript widget that can be embedded into any web page. The widget provides an AI-powered chat interface using the `genassist-chat-react` component. It is built as an IIFE (Immediately Invoked Function Expression) bundle that includes all dependencies (React, ReactDOM, GenAgentChat).

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- A Genassist API account with `baseUrl`, `apiKey`, and `tenant` ID

### Installation

```bash
npm install
```

### Configuration

Before running or building, create your local configuration file:

```bash
cp src/config/config.example.js src/config/config.js
```

Then edit `src/config/config.js` with your API credentials and settings. This file is **gitignored** and will not be committed.

> **Note:** `src/config/config.js` is imported in `main.jsx` and sets `window.GENASSIST_CONFIG` at build time, so the configuration is bundled into the widget. For external/runtime configuration, you can comment out the import in `main.jsx` and set `window.GENASSIST_CONFIG` directly in your HTML page instead.

### Development

```bash
npm run dev
```

### Building

```bash
npm run build
```

This produces the following files in the `dist/` directory:

| File | Description |
|------|-------------|
| `widget.iife.js` | The self-contained widget JavaScript bundle |
| `widget.css` | The extracted CSS styles |

> **Note:** The build excludes images and static assets. Only JS and CSS files are output.

### Local Preview

```bash
npm run serve
```

This builds the widget and serves the `example-widget/` directory on `http://localhost:8022`.

## Usage

### Quick Integration

1. **Build the widget:**
   ```bash
   npm run build
   ```

2. **Upload to CDN:**
   Upload `dist/widget.iife.js` and `dist/widget.css` to your CDN or static hosting service.

3. **Add to your page:**
   ```html
   <div id="genassist-chat-root"></div>

   <script>
     window.GENASSIST_CONFIG = {
       baseUrl: 'https://your-api-url.com',
       apiKey: 'your-api-key',
       tenant: 'your-tenant-id',
       headerTitle: 'GenAssist',
       placeholder: 'Ask anything...',
       mode: 'floating',
       floatingConfig: { position: 'bottom-right' },
       serverUnavailableMessage: 'Support is currently offline.',
       noColorAnimation: true,
       useWs: false,
       useFiles: false
     };
   </script>
   <link rel="stylesheet" href="https://your-cdn-url.com/widget.css">
   <script src="https://your-cdn-url.com/widget.iife.js"></script>
   ```

### Dynamic Integration (JavaScript Render Form)

For platforms that use JavaScript render forms (e.g., Zendesk Help Center), see `example-widget/integration.js` for a ready-to-use script that dynamically creates the root element and loads the widget.

### Configuration

The widget reads its configuration from `window.GENASSIST_CONFIG`:

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `baseUrl` | string | Yes | Your Genassist API base URL |
| `apiKey` | string | Yes | Your API key |
| `tenant` | string | Yes | Your tenant ID |
| `headerTitle` | string | No | Title displayed in the chat header |
| `agentName` | string | No | Name of the agent |
| `description` | string | No | Agent description text |
| `logoUrl` | string | No | URL for the agent logo |
| `placeholder` | string | No | Placeholder text for the input field |
| `mode` | string | No | Display mode: `"floating"` or `"embedded"` |
| `floatingConfig` | object | No | Configuration for floating mode (e.g., `{ position: 'bottom-right' }`) |
| `serverUnavailableMessage` | string | No | Message shown when server is unavailable |
| `noColorAnimation` | boolean | No | Disable color animation |
| `useWs` | boolean | Yes | Enable or disable WebSocket connection |
| `useFiles` | boolean | No | Enable or disable file uploads |
| `theme` | object | No | Theme customization (see below) |
| `userData` | object | No | User information (`email`, `name`, `userId`) |

### Theme Configuration

```javascript
theme: {
  primaryColor: '#4F46E5',
  secondaryColor: '#f5f5f5',
  backgroundColor: '#ffffff',
  textColor: '#000000',
  fontFamily: 'Roboto, sans-serif',
  fontSize: '14px'
}
```

## Custom Fonts

The widget ships with the **Roboto** font bundled via `@font-face` declarations in `src/font.css`. The font files are located in `src/fonts/` and are embedded into `widget.css` during the build.

To use a **custom font** instead:

1. **Edit `src/font.css`** — Replace the existing `@font-face` rules with your own font declarations:
   ```css
   @font-face {
     font-family: "YourFont";
     src: url("./fonts/YourFont/YourFont-Regular.ttf") format("truetype");
     font-weight: 400;
     font-style: normal;
   }
   ```

2. **Add your font files** to `src/fonts/`.

3. **Set the font in the theme config:**
   ```javascript
   window.GENASSIST_CONFIG = {
     // ...
     theme: {
       fontFamily: 'YourFont, sans-serif'
     }
   };
   ```

4. **Rebuild** — The font will be bundled into `widget.css` automatically.

> **Tip:** If you prefer to load fonts externally (e.g., from Google Fonts), you can remove the `@font-face` rules from `src/font.css` and add a `<link>` tag to your page instead. See the example in `example-widget/index.html`.

## Project Structure

```
├── src/
│   ├── main.jsx              # Widget entry point and bootstrap logic
│   ├── font.css              # @font-face declarations for bundled fonts
│   ├── index.css             # Optional global style overrides (commented out by default)
│   ├── fonts/                # Font files (Roboto)
│   └── config/
│       ├── config.example.js # Template config (committed to git)
│       └── config.js         # Your local config (gitignored)
├── dist/                     # Build output (generated)
│   ├── widget.iife.js        # Widget JS bundle
│   └── widget.css            # Widget styles
├── example-widget/           # Integration examples
│   ├── index.html            # Standalone HTML demo page
│   └── integration.js        # Dynamic loader for JS render forms
└── vite.config.js            # Vite build configuration
```

## How It Works

1. The widget looks for a `<div>` with id `genassist-chat-root` in the DOM
2. It reads configuration from `window.GENASSIST_CONFIG`
3. It renders the `GenAgentChat` React component into the root element
4. The widget auto-initializes when the script loads, or can be manually triggered via `window.GenassistBootstrap()`

## Troubleshooting

### Widget not appearing

1. Ensure the root element exists: `<div id="genassist-chat-root"></div>`
2. Verify `window.GENASSIST_CONFIG` is set **before** the widget script loads
3. Check the browser console for errors
4. Verify the widget script URL is correct and accessible

### Build issues

1. Ensure all dependencies are installed: `npm install`
2. Check that `genassist-chat-react` is properly installed
3. Review build output for errors
