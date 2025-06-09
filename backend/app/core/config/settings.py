from pathlib import Path
from typing import Optional, Tuple
from pydantic import computed_field, ConfigDict
from pydantic_settings import BaseSettings
import os


class ProjectSettings(BaseSettings):

    def __init__(self, **values):
        super().__init__(**values)
        if self.REDIS_HOST is None:
            self.REDIS_HOST = "127.0.0.1" if self.DEV else "redis"


    # === Redis Configuration ===
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    FERNET_KEY: Optional[str]

    # === LLM Keys ===
    OPENAI_API_KEY: Optional[str] = None
    HUGGINGFACE_TOKEN: Optional[str] = None

    # === Whisper Model Defaults ===
    DEFAULT_WHISPER_MODEL: str = "base.en"
    SUPPORTED_AUDIO_FORMATS: Tuple[str, ...] = ("mp3", "mp4", "mpweg", "mpga", "m4a", "wav", "webm")

    # === File Storage ===
    UPLOAD_FOLDER: str = os.path.join(os.getcwd(), "uploads")
    AGENT_FOLDER: str = os.path.join(os.getcwd(), "uploads/agents")
    RECORDINGS_DIR: Path = Path(os.getcwd()) / "recordings"

    # === Limits ===
    MAX_CONTENT_LENGTH: int = 50 * 1024 * 1024  # 50MB
    DEFAULT_WINDOW_SECONDS: int = 60

    # === Language ===
    DEFAULT_LANGUAGE: str = 'en'
    SUPPORTED_LANGUAGES: Tuple[str, ...] = ('en',)
    DEFAULT_OPEN_AI_GPT_MODEL: str = "gpt-4o"

    # === Database ===
    DB_HOST: Optional[str]
    DB_USER: Optional[str]
    DB_PASS: Optional[str]
    DB_NAME: Optional[str]
    CREATE_DB: bool = False
    DB_ASYNC: bool = True
    
    DEBUG: bool = True
    DEV: bool = True
    FASTAPI_DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    SQLALCHEMY_LOG_LEVEL: str = "ERROR"
    FASTAPI_RUN_PORT: int = 8000
    AUTO_MIGRATE: int = True  # for alembic migration on startup
    API_VERSION: Optional[str] = "1.0"
    
    ZENDESK_SUBDOMAIN:     Optional[str] = ""
    ZENDESK_EMAIL:         Optional[str] = ""
    ZENDESK_API_TOKEN:     Optional[str] = ""
    ZENDESK_CUSTOM_FIELD_CONVERSATION_ID: Optional[int] = 0

    @property
    def _zendesk_base(self) -> str:
        return f"https://{self.ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"

    @property
    def _zendesk_auth(self) -> tuple[str,str]:
        return (f"{self.ZENDESK_EMAIL}/token", self.ZENDESK_API_TOKEN)

    
    
    @computed_field
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}/{self.DB_NAME}"

    @computed_field
    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}/{self.DB_NAME}"


    model_config = ConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",  # ignore unknown fields instead of raising an error
            )


settings = ProjectSettings()
