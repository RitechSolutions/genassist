# Genassist Widget - Integration Examples

This directory contains examples for integrating the Genassist widget by using JavaScript render forms.

## Files
- `example.html` - Complete example HTML file demonstrating the integration
- `integration.js` - Standalone JavaScript code

## 🚀 Quick Start - Running the Example

**Step 1:** Build the widget
```bash
npm run build
```

**Step 2:** Start a local server (choose one method)

**Option A - Using the serve script (easiest, from project root):**
```bash
# Build the widget first
npm run build

# Then run the serve script
bash examples/serve.sh
```
Then open: `http://localhost:8000/examples/zendesk-hc-example.html`

**Option A2 - Using npm scripts (from project root):**
```bash
# Build the widget first
npm run example:build

# Then start a server (in a separate terminal, from project root)
npm run example:serve
```
Then open: `http://localhost:8000/examples/zendesk-hc-example.html`

**Option B - Python (if installed, from project root):**
```bash
# Make sure you're in the project root directory
python3 -m http.server 8000
```
Then open: `http://localhost:8000/examples/zendesk-hc-example.html`

**Option C - Node.js http-server (from project root):**
```bash
# Make sure you're in the project root directory
npx http-server -p 8000
```
Then open: `http://localhost:8000/examples/zendesk-hc-example.html`

**Option D - Using Vite preview:**
```bash
npm run preview
```
Then navigate to the examples folder in the preview URL.

**Step 4:** Configure and test
- Update the `window.GENASSIST_CONFIG` in the HTML with your API credentials
- Click "Initialize Widget" button to test

## Quick Start

### Option 1: Using JavaScript Render Form in Zendesk

1. **Build the widget:**
   ```bash
   npm run build
   ```

2. **Upload the widget to a CDN:**
   - Upload `dist/widget.iife.js` to your CDN or static hosting
   - Note the public URL

3. **Add to Zendesk Help Center:**
   - Go to your Zendesk Help Center theme customization
   - Navigate to the JavaScript render form
   - Add the code from `zendesk-integration.js`
   - Update the configuration values (baseUrl, apiKey, tenant, etc.)
   - Update the widget script URL to point to your CDN

### Option 2: Local Testing

1. **Install dependencies (if not already done):**
   ```bash
   npm install
   ```

2. **Build the widget:**
   ```bash
   npm run build
   ```
   This creates `dist/widget.iife.js` which the example needs.

3. **Run the example:**
   
   **Method A: Using a local server (Recommended)**
   
   You can use any local HTTP server. Here are a few options:
   
   **Using Python:**
   ```bash
   # Python 3
   cd examples
   python3 -m http.server 8000
   ```
   Then open: http://localhost:8000/zendesk-hc-example.html
   
   **Using Node.js (http-server):**
   ```bash
   # Install http-server globally (if not installed)
   npm install -g http-server
   
   # Run from project root
   http-server -p 8000
   ```
   Then open: http://localhost:8000/examples/zendesk-hc-example.html
   
   **Using Vite preview:**
   ```bash
   npm run build
   npm run preview
   ```
   Then navigate to the examples folder in the preview URL.
   
   **Method B: Direct file opening (may have CORS issues)**
   - Simply open `examples/zendesk-hc-example.html` directly in your browser
   - Note: Some browsers may block loading the widget.iife.js file due to CORS policies
   - If you see CORS errors, use Method A instead

4. **Configure the widget:**
   - Before testing, update the configuration in `zendesk-hc-example.html`:
     - Set your `baseUrl`
     - Set your `apiKey`
     - Set your `tenant` ID
   - Or use the default placeholder values to see the widget structure (it won't connect without real credentials)

5. **Initialize the widget:**
   - Click the "Initialize Widget" button on the example page
   - Or uncomment the script tag in the HTML for auto-loading

## Configuration Options

The widget accepts the following configuration options via `window.GENASSIST_CONFIG`:

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `baseUrl` | string | Yes | Your Genassist API base URL |
| `apiKey` | string | Yes | Your API key |
| `tenant` | string | Yes | Your tenant ID |
| `headerTitle` | string | No | Title displayed in the chat header (default: "Genassist Chat") |
| `placeholder` | string | No | Placeholder text for the input field |
| `theme` | object | No | Theme customization object |
| `theme.primaryColor` | string | No | Primary color for the UI |
| `theme.backgroundColor` | string | No | Background color |
| `theme.textColor` | string | No | Text color |
| `theme.fontFamily` | string | No | Font family |
| `theme.fontSize` | string | No | Font size |
| `mode` | string | No | Display mode: "floating" or "embedded" |
| `floatingConfig` | object | No | Configuration for floating mode |
| `floatingConfig.position` | string | No | Position: "bottom-right", "bottom-left", "top-right", "top-left" |
| `userData` | object | No | User information (email, name, userId) |
| `onError` | function | No | Error callback function |
| `onTakeover` | function | No | Agent takeover callback function |
| `useWS` | boolean | No | 

## Zendesk-Specific Integration

### Getting User Data from Zendesk

You can extract user information from Zendesk's Help Center API:

```javascript
// Example: Get current user from Zendesk
if (window.HelpCenter && window.HelpCenter.user) {
  window.GENASSIST_CONFIG.userData = {
    email: window.HelpCenter.user.email,
    name: window.HelpCenter.user.name,
    userId: window.HelpCenter.user.id
  };
}
```

### Conditional Loading

You can conditionally load the widget based on page or user:

```javascript
// Only load on article pages
if (document.body.classList.contains('article-page')) {
  // Initialize widget
}

// Only load for authenticated users
if (window.HelpCenter && window.HelpCenter.user) {
  // Initialize widget
}
```

## Troubleshooting

### 404 Not Found Error

If you get a 404 error when accessing the example:

1. **Stop the current server** (Ctrl+C) and restart it:
   ```bash
   # Make sure you're in project root
   cd ~/genassist-plugin-js
   
   # Kill any existing server on port 8000
   lsof -ti:8000 | xargs kill -9 2>/dev/null || true
   
   # Restart the server
   npm run serve
   ```

2. **Verify you're running the server from the project root:**
   ```bash
   # Check your current directory
   pwd
   # Should show: .../plugin-js
   
   # If not, navigate to project root:
   cd ~/plugin-js
   ```

3. **Verify the file exists:**
   ```bash
   ls example-widget/example.html
   # Should show the file
   ```

4. **Try using Python's http.server instead:**
   ```bash
   python3 -m http.server 9000
   ```
   Then access: `http://localhost:9000/examples/zendesk-hc-example.html`

5. **Or use the serve script:**
   ```bash
   bash example-widget/serve.sh
   ```

6. **Check the server is running:**
   - Make sure the server started successfully
   - Check the port number (should be 9000)
   - Try accessing: `http://localhost:9000/` first to see the directory listing
   - Look for "examples" in the directory listing

7. **Verify the widget file exists:**
   ```bash
   ls dist/widget.iife.js
   ls dist/widget.iife.css
   # Should show the file (after running npm run build)
   ```

### Widget not appearing

1. Check that the root element exists: `<div id="genassist-chat-root"></div>`
2. Verify the widget script is loading (check browser console)
3. Ensure `window.GENASSIST_CONFIG` is set before the script loads
4. Check for JavaScript errors in the browser console

### Styling conflicts

If the widget styling conflicts with your Zendesk theme:

1. Adjust the `theme` configuration
2. Use CSS to override styles if needed
3. Consider using `mode: 'embedded'` instead of `floating`

### Build issues

If the build fails:

1. Ensure all dependencies are installed: `npm install`
2. Check that `genassist-chat-react` is properly installed
3. Review the build output for errors

## Support

For issues or questions, please refer to the main project README or contact support.

