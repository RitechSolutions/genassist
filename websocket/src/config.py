from typing import Optional
from urllib.parse import quote, unquote

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_USER: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_SSL: bool = False

    # Backend
    BACKEND_URL: str = "http://localhost:8000"
    WS_INTERNAL_SECRET: str = "websocket-internal-secret"

    # WebSocket service
    HOST: str = "0.0.0.0"
    WS_PORT: int = 8002
    LOG_LEVEL: str = "info"

    # Heartbeat
    HEARTBEAT_INTERVAL: int = 30  # seconds between pings
    HEARTBEAT_TIMEOUT: int = 10  # seconds to wait for pong

    # Auth cache
    AUTH_CACHE_MAX_SIZE: int = 10000

    # OpenAI (for TTS endpoint)
    OPENAI_API_KEY: Optional[str] = None

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        host = self.REDIS_HOST
        if self.REDIS_PASSWORD:
            auth = f"{quote(self.REDIS_USER or '', safe='')}:{quote(self.REDIS_PASSWORD, safe='')}@"
        else:
            auth = ""
        scheme = "rediss" if self.REDIS_SSL else "redis"
        return unquote(f"{scheme}://{auth}{host}:{self.REDIS_PORT}/{self.REDIS_DB}")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
