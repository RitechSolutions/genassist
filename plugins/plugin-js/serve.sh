#!/bin/bash
# Simple script to serve the example
# Run from project root: bash example-widget/serve.sh

# Copy the dist files to the example-widget folder and replace the existing ones
rm -rf example-widget/dist && cp -r dist example-widget/

# Serve the example-widget folder
cd example-widget || exit

echo "Serving from: $(pwd)"
echo "Open: http://localhost:8022/index.html"
echo "Press Ctrl+C to stop"
echo ""

# # Use http-server to serve the example-widget folder
# npx http-server -p 8022 -c-1

# Try Python first, then fall back to http-server
if command -v python3 &> /dev/null; then
    python3 -m http.server 8022
elif command -v python &> /dev/null; then
    python -m http.server 8022
else
    npx http-server -p 8022 -c-1 --cors
fi

