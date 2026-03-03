"""Run the WebSocket service with uvicorn."""
import sys
from pathlib import Path

import uvicorn

# Ensure repository root is on sys.path so shared packages like `backend_shared` resolve
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Settings

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run("main:app", host=settings.HOST, port=settings.WS_PORT, app_dir="src")
