#!/bin/sh
set -e

# ---------------------------------------------------------------------------
# Runtime environment variable substitution
# Replaces build-time placeholders in the JS bundle with actual env var values
# passed to the container. This allows the same image to run in any environment.
# ---------------------------------------------------------------------------

JS_DIR="/usr/share/nginx/html/assets"

if [ -d "$JS_DIR" ]; then
  echo "=== Injecting runtime environment variables ==="
  for file in "$JS_DIR"/*.js; do
    [ -f "$file" ] || continue
    sed -i "s|__VITE_UI_VERSION__|${VITE_UI_VERSION:-}|g" "$file"
    sed -i "s|__VITE_PUBLIC_API_URL__|${VITE_PUBLIC_API_URL:-}|g" "$file"
    sed -i "s|__VITE_WEBSOCKET_PUBLIC_URL__|${VITE_WEBSOCKET_PUBLIC_URL:-}|g" "$file"
    sed -i "s|__VITE_GENASSIST_CHAT_APIKEY__|${VITE_GENASSIST_CHAT_APIKEY:-}|g" "$file"
    sed -i "s|__VITE_MULTI_TENANT_ENABLED__|${VITE_MULTI_TENANT_ENABLED:-true}|g" "$file"
    sed -i "s|__VITE_WS__|${VITE_WS:-true}|g" "$file"
    sed -i "s|__VITE_ONBOARDING_API_URL__|${VITE_ONBOARDING_API_URL:-}|g" "$file"
    sed -i "s|__VITE_ONBOARDING_CHAT_APIKEY__|${VITE_ONBOARDING_CHAT_APIKEY:-}|g" "$file"
    sed -i "s|__VITE_ONBOARDING_USERNAME__|${VITE_ONBOARDING_USERNAME:-}|g" "$file"
    sed -i "s|__VITE_ONBOARDING_PASSWORD__|${VITE_ONBOARDING_PASSWORD:-}|g" "$file"
    sed -i "s|__VITE_GENASSIST_CHAT_TENANT_ID__|${VITE_GENASSIST_CHAT_TENANT_ID:-}|g" "$file"
  done
  echo "=== Environment variables injected ==="
fi

# Start nginx
nginx -g 'daemon off;'
