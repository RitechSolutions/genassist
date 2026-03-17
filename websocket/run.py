"""Run the WebSocket service with uvicorn."""
import uvicorn

from src.config import Settings

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run("main:app", host=settings.HOST, port=settings.WS_PORT, app_dir="src")
