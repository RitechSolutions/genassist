#!/usr/bin/env bash
set -euo pipefail

# Detect the active env that launched pre-commit
ENV_NAME=$(conda info --json | python -c "import json,sys; print(json.load(sys.stdin)['active_prefix_name'])")

# Export without build hashes so CI remains platform-agnostic
conda env export --no-builds -n "$ENV_NAME" > environment.yml

# Stage the fresh file so it lands in the commit
git add environment.yml