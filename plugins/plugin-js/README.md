# Genassist Widget Plugin (JavaScript)

A React-based widget plugin for integrating Genassist chat into any website using a standalone JavaScript bundle.

## Overview

This project builds a standalone JavaScript widget that can be embedded into any web page. The widget provides an AI-powered chat interface using the `genassist-chat-react` component. It is built as an IIFE (Immediately Invoked Function Expression) bundle that includes all dependencies (React, ReactDOM, GenAgentChat).

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- A Genassist API account with `baseUrl`, `apiKey`, and optionally `tenant` ID

### Installation

```bash
npm install
```

### Configuration

Configuration is set via `window.GENASSIST_CONFIG` in your HTML page **before** the widget script loads. The widget reads this configuration object at initialization and whenever `window.GenassistBootstrap()` is called.

> **Note:** Configuration should be set before the widget script loads, or you can update it dynamically and call `window.GenassistBootstrap()` to re-render with the new values.

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

For platforms that use JavaScript render forms (e.g., Zendesk Help Center), see `example-widget/index.html` for a ready-to-use example that demonstrates how to dynamically create the root element and load the widget.

### Configuration

The widget reads its configuration from `window.GENASSIST_CONFIG`:

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `baseUrl` | string | Yes | Your Genassist API base URL |
| `apiKey` | string | Yes | Your API key |
| `tenant` | string | No | Your tenant ID |
| `headerTitle` | string | No | Title displayed in the chat header (default: "GenAssist") |
| `agentName` | string | No | Name of the agent (default: "GenAssist") |
| `description` | string | No | Agent description text (default: "Your Virtual Assistant") |
| `logoUrl` | string | No | URL for the agent logo |
| `placeholder` | string | No | Placeholder text for the input field (default: "Ask a question") |
| `mode` | string | No | Display mode: `"floating"` or `"embedded"` (default: "floating") |
| `floatingConfig` | object | No | Configuration for floating mode (e.g., `{ position: 'bottom-right' }`) |
| `serverUnavailableMessage` | string | No | Message shown when server is unavailable |
| `noColorAnimation` | boolean | No | Disable color animation (default: true) |
| `useWs` | boolean | No | Enable or disable WebSocket connection (default: false) |
| `useFiles` | boolean | No | Enable or disable file uploads (default: false) |
| `theme` | object | No | Theme customization (see below) |

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
│   └── fonts/                # Font files (Roboto)
├── dist/                     # Build output (generated)
│   ├── widget.iife.js        # Widget JS bundle
│   └── widget.css            # Widget styles
├── example-widget/           # Integration examples
│   ├── dist                  # Distributed assets (copied from dist/ during serve)
│   ├── index.html            # Standalone HTML demo page
│   └── README.md             # Example integration guide
├── serve.sh                  # Script to serve example-widget locally
└── vite.config.js            # Vite build configuration
```

## How It Works

1. The widget looks for a `<div>` with id `genassist-chat-root` in the DOM
2. It reads configuration from `window.GENASSIST_CONFIG`
3. It renders the `GenAgentChat` React component into the root element
4. The widget auto-initializes when the script loads, or can be manually triggered via `window.GenassistBootstrap()`

### Dynamic Configuration Updates

The widget supports updating configuration at runtime. After modifying `window.GENASSIST_CONFIG`, call `window.GenassistBootstrap()` to re-render the widget with the new configuration:

```javascript
// Update configuration
window.GENASSIST_CONFIG = {
  ...window.GENASSIST_CONFIG,
  headerTitle: "New Title",
  noColorAnimation: false,
  theme: {
    primaryColor: "#FF5733"
  }
};

// Re-render with new config
window.GenassistBootstrap();
```

The bootstrap function safely reuses the existing React root, so you can call it multiple times without performance issues.

> **Note:** Configuration values use nullish coalescing (`??`) for defaults, which means explicit `false` or empty string values will be respected. For example, setting `noColorAnimation: false` will properly disable animations, unlike using logical OR (`||`) which would treat `false` as falsy and use the default.

## Troubleshooting

### Widget not appearing

1. Ensure the root element exists: `<div id="genassist-chat-root"></div>`
2. Verify `window.GENASSIST_CONFIG` is set **before** the widget script loads (or call `window.GenassistBootstrap()` after setting it)
3. Check the browser console for errors
4. Verify the widget script URL is correct and accessible

### Configuration not updating

If you've updated `window.GENASSIST_CONFIG` but the widget hasn't changed:

1. Make sure you're calling `window.GenassistBootstrap()` after updating the config
2. Verify the config object is being set correctly: `console.log(window.GENASSIST_CONFIG)`
3. Check that you're using the correct property names (case-sensitive)
4. Remember that `false` and empty string values are now respected (unlike before with `||` defaults)

### Build issues

1. Ensure all dependencies are installed: `npm install`
2. Check that `genassist-chat-react` is properly installed
3. Review build output for errors
