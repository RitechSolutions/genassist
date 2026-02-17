# Genassist Widget - Integration Example

This directory contains an example for integrating the Genassist widget using JavaScript render forms.

## Files
- `index.html` - Complete example HTML file demonstrating the integration

## 🚀 Quick Start - Running the Example

**Step 1:** Build the widget
```bash
npm run build
```

**Step 2:** Start a local server

**Option A - Using the serve script (recommended, from project root):**
```bash
npm run serve
```
Then open: `http://localhost:8022/index.html`

**Option B - Using the serve script directly:**
```bash
# Build the widget first
npm run build

# Then run the serve script
bash serve.sh
```
Then open: `http://localhost:8022/index.html`

**Option C - Python (if installed):**
```bash
# Build first
npm run build

# Copy the dist files to the example-widget folder and replace the existing ones
rm -rf example-widget/dist && cp -r dist example-widget/

# Copy example-widget/config/config.example.js to example-widget/config/config.js and use your configurations

# Serve from example-widget directory
cd example-widget
python3 -m http.server 8022
```
Then open: `http://localhost:8022/index.html`

**Step 3:** Configure and test
- Update the `window.GENASSIST_CONFIG` in `index.html` with your API credentials
- The widget will automatically initialize when the page loads

## Quick Integration Guide

### Option 1: Using JavaScript Render Form (e.g., Zendesk Help Center)

1. **Build the widget:**
   ```bash
   npm run build
   ```

2. **Upload the widget to a CDN:**
   - Upload `dist/widget.iife.js` and `dist/widget.css` to your CDN or static hosting
   - Note the public URLs

3. **Add to your platform:**
   - Go to your platform's JavaScript render form (e.g., Zendesk Help Center theme customization)
   - Add the code from `index.html` (see the "Step 2: Complete Example Integration" section)
   - Update the configuration values (baseUrl, apiKey, tenant, etc.)
   - Update the widget script and CSS URLs to point to your CDN

### Option 2: Local Testing

1. **Install dependencies (if not already done):**
   ```bash
   npm install
   ```

2. **Build the widget:**
   ```bash
   npm run build
   ```
   This creates `dist/widget.iife.js` and `dist/widget.css` which the example needs.

3. **Run the example:**
   ```bash
   npm run serve
   ```
   Then open: `http://localhost:8022/index.html`

4. **Configure the widget:**
   - Update the configuration in `index.html`:
     - Set your `baseUrl`
     - Set your `apiKey`
     - Set your `tenant` ID
   - Or use the default placeholder values to see the widget structure (it won't connect without real credentials)

## Configuration Options

The widget accepts the following configuration options via `window.GENASSIST_CONFIG`:

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
| `mode` | string | No | Display mode: "floating" or "embedded" (default: "floating") |
| `floatingConfig` | object | No | Configuration for floating mode |
| `floatingConfig.position` | string | No | Position: "bottom-right", "bottom-left", "top-right", "top-left" |
| `serverUnavailableMessage` | string | No | Message shown when server is unavailable |
| `noColorAnimation` | boolean | No | Disable color animation (default: true) |
| `useWs` | boolean | No | Enable or disable WebSocket connection (default: false) |
| `useFiles` | boolean | No | Enable or disable file uploads (default: false) |
| `theme` | object | No | Theme customization object |
| `theme.primaryColor` | string | No | Primary color for the UI |
| `theme.secondaryColor` | string | No | Secondary color |
| `theme.backgroundColor` | string | No | Background color |
| `theme.textColor` | string | No | Text color |
| `theme.fontFamily` | string | No | Font family |
| `theme.fontSize` | string | No | Font size |

## Troubleshooting

### Widget not appearing

1. Check that the root element exists: `<div id="genassist-chat-root"></div>`
2. Verify the widget script is loading (check browser console)
3. Ensure `window.GENASSIST_CONFIG` is set before the script loads
4. Check for JavaScript errors in the browser console
5. Verify the widget files (`widget.iife.js` and `widget.css`) are accessible

### Configuration not updating

If you've updated `window.GENASSIST_CONFIG` but the widget hasn't changed:

1. Make sure you're calling `window.GenassistBootstrap()` after updating the config
2. Verify the config object is being set correctly: `console.log(window.GENASSIST_CONFIG)`
3. Check that you're using the correct property names (case-sensitive)

### Build issues

If the build fails:

1. Ensure all dependencies are installed: `npm install`
2. Check that `genassist-chat-react` is properly installed
3. Review the build output for errors

### Server not starting

If the serve script doesn't work:

1. Make sure you've built the widget first: `npm run build`
2. Verify Python 3 or Node.js is installed
3. Check that port 8022 is not already in use
4. Try running the serve script manually: `bash serve.sh`

## Support

For issues or questions, please refer to the main project README or contact support.
