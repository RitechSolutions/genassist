#!/bin/bash
set -e

# Create required directories in the mounted volume
mkdir -p /src/datavolume/logs

# Start the application
exec python /src/run.py
