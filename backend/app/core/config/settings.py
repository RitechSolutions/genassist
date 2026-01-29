from typing import Optional, Tuple
from urllib.parse import quote, unquote 

from pydantic import computed_field, ConfigDict, Field
from pydantic_settings import BaseSettings

from app.core.project_path import DATA_VOLUME


class ProjectSettings(BaseSettings):

    def __init__(self, **values):
        super().__init__(**values)
    # === Redis Configuration ===
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None  # Auth; included in REDIS_URL when set
    REDIS_FOR_CONVERSATION: bool = True
    # Memory efficiency settings for Redis conversations
    CONVERSATION_MAX_MEMORY_MESSAGES: int = 50  # Max messages kept in memory
    CONVERSATION_REDIS_EXPIRY_DAYS: int = 30  # Redis data expiration
    # Redis connection pool settings
    # For 300-500 concurrent WebSocket users, 30-40 connections is optimal
    # Each publish takes ~5ms, so connections are rapidly reused
    REDIS_MAX_CONNECTIONS: int = 40  # Max connections in pool
    REDIS_MAX_CONNECTIONS_FOR_ENDPOINT_CACHE: int = 20 # Used to cache agents, etc, in services
    REDIS_SOCKET_TIMEOUT: int = 5  # Socket timeout in seconds
    REDIS_HEALTH_CHECK_INTERVAL: int = 30  # Health check interval in seconds

    # Celery Redis connection pool settings
    CELERY_REDIS_MAX_CONNECTIONS: int = 50  # Max connections for Celery broker & backend
    # Worker pool: "solo" avoids SIGSEGV with PyTorch/transformers/sentence-transformers (app tasks load these).
    # Use "prefork" only if you run workers that do not import ML libs; set CELERY_WORKER_POOL=prefork.
    CELERY_WORKER_POOL: str = "solo"

    FERNET_KEY: Optional[str]

    # === LLM Keys ===
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    HUGGINGFACE_TOKEN: Optional[str] = None

    # === Whisper Model Defaults ===
    DEFAULT_WHISPER_MODEL: str = "base.en"
    SUPPORTED_AUDIO_FORMATS: Tuple[str, ...] = (
        "mp3",
        "mp4",
        "mpeg",
        "mpga",
        "m4a",
        "wav",
        "webm",
    )
    WHISPER_TRANSCRIBE_SERVICE: str = "http://localhost:8001/transcribe"

    # === File Storage ===
    UPLOAD_FOLDER: str = str(DATA_VOLUME / "uploads")
    AGENT_FOLDER: str = str(DATA_VOLUME / "uploads/agents")
    RECORDINGS_DIR: str = str(DATA_VOLUME / "recordings")

    # === Limits ===
    MAX_CONTENT_LENGTH: int = 50 * 1024 * 1024  # 50MB
    DEFAULT_WINDOW_SECONDS: int = 60

    # === Language ===
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: Tuple[str, ...] = ("en",)
    DEFAULT_OPEN_AI_GPT_MODEL: str = "gpt-4o"

    # === Database ===
    DB_HOST: Optional[str]
    DB_USER: Optional[str]
    DB_PASS: Optional[str]
    DB_NAME: Optional[str]
    DB_PORT: Optional[int]
    CREATE_DB: bool = False
    DB_ASYNC: bool = True
    # SQLAlchemy async engine pool settings
    DB_POOL_SIZE: int = 100
    DB_MAX_OVERFLOW: int = 100
    DB_POOL_TIMEOUT: int = 30  # seconds
    DB_POOL_RECYCLE: int = 1800  # seconds

    # === Multi-Tenancy ===
    MULTI_TENANT_ENABLED: bool = False
    TENANT_HEADER_NAME: str = "x-tenant-id"
    TENANT_SUBDOMAIN_ENABLED: bool = False

    DEBUG: bool = True
    DEV: bool = False
    FASTAPI_DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    SQLALCHEMY_LOG_LEVEL: str = "ERROR"
    FASTAPI_RUN_PORT: int = 8000
    # for alembic migration on startup (changed type from int to bool)
    AUTO_MIGRATE: bool = True
    API_VERSION: Optional[str] = "1.0"
    OPENAPI_PATH: str = "openapi.json"
    WHATSAPP_TOKEN: str = "<enter-value-here>"

    SLACK_TOKEN: str = "<enter-value-here>"
    SLACK_SIGNING_SECRET: str = "<enter-value-here>"

    GMAIL_CLIENT_ID: Optional[str] = "<enter-value-here>"
    GMAIL_CLIENT_SECRET: Optional[str] = "<enter-value-here>"

    MICROSOFT_CLIENT_ID: Optional[str] = "<enter-value-here>"
    MICROSOFT_CLIENT_SECRET: Optional[str] = "<enter-value-here>"
    MICROSOFT_TENANT_ID: Optional[str] = "<enter-value-here>"

    ZENDESK_SUBDOMAIN: Optional[str] = "<enter-value-here>"
    ZENDESK_EMAIL: Optional[str] = "<enter-value-here>"
    ZENDESK_API_TOKEN: Optional[str] = "<enter-value-here>"
    ZENDESK_CUSTOM_FIELD_CONVERSATION_ID: Optional[int] = 0

    AWS_RECORDINGS_BUCKET: Optional[str] = "genassist-dev-temp-bucket"
    AWS_S3_TEST_BUCKET: Optional[str] = "genassist-dev-temp-bucket"

    # Service calling
    DEFAULT_TIMEOUT: float = 200.0
    CONNECT_TIMEOUT: float = 5.0
    MAX_CONNECTIONS: int = 20
    MAX_KEEPALIVE_CONNECTIONS: int = 10

    # Test credentials
    TEST_USERNAME: Optional[str] = "test"
    TEST_PASSWORD: Optional[str] = "test"

    # Check if inside celery container
    BACKGROUND_TASK: bool = False

    # === CORS Configuration ===
    CORS_ALLOWED_ORIGINS: Optional[str] = (
        None  # Comma-separated list of additional allowed origins
    )

    # === Rate Limiting Configuration ===
    RATE_LIMIT_ENABLED: bool = False
    # Global rate limit: requests per time window
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    # Auth endpoints rate limit (stricter)
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    RATE_LIMIT_AUTH_PER_HOUR: int = 20
    # Conversation endpoints rate limits
    RATE_LIMIT_CONVERSATION_START_PER_MINUTE: int = 10
    RATE_LIMIT_CONVERSATION_START_PER_HOUR: int = 100
    RATE_LIMIT_CONVERSATION_UPDATE_PER_MINUTE: int = 30
    RATE_LIMIT_CONVERSATION_UPDATE_PER_HOUR: int = 500
    # Rate limit storage backend (redis or memory)
    RATE_LIMIT_STORAGE_BACKEND: str = "redis"  # "redis" or "memory"

    # === Chroma Configuration ===
    CHROMA_HOST: str = Field(default="localhost", description="Database host")
    CHROMA_PORT: int = Field(default=8005, description="Database port")

    @property
    def _zendesk_base(self) -> str:
        return f"https://{self.ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"

    @property
    def _zendesk_auth(self) -> tuple[str, str]:
        return (f"{self.ZENDESK_EMAIL}/token", self.ZENDESK_API_TOKEN)

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        host = self.REDIS_HOST or "localhost"
        if self.REDIS_PASSWORD:
            auth = f":{quote(self.REDIS_PASSWORD, safe='')}@"
        else:
            auth = ""
        return f"redis://{auth}{host}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        user = quote(self.DB_USER or "", safe="")
        password = quote(self.DB_PASS or "", safe="")
        return  unquote(f"postgresql+asyncpg://{user}:{password}@{self.DB_HOST}/{self.DB_NAME}")

    @computed_field
    @property
    def DATABASE_URL_SYNC(self) -> str:
        user = quote(self.DB_USER or "", safe="")
        password = quote(self.DB_PASS or "", safe="")
        return unquote(f"postgresql+psycopg2://{user}:{password}@{self.DB_HOST}/{self.DB_NAME}")

    @computed_field
    @property
    def POSTGRES_URL(self) -> str:
        user = quote(self.DB_USER or "", safe="")
        password = quote(self.DB_PASS or "", safe="")
        return unquote(f"postgresql://{user}:{password}@{self.DB_HOST}/postgres")

    def get_tenant_database_name(self, tenant: str = "master") -> str:
        if tenant == "master":
            return self.DB_NAME
        else:
            return f"{self.DB_NAME}_tenant_{tenant.replace('-', '_')}"

    def get_tenant_database_url(self, tenant: str = "master") -> str:
        """Generate database URL for a specific tenant"""
        # Sanitize tenant_id for database name (replace hyphens with underscores)
        tenant_db = self.get_tenant_database_name(tenant)
        user = quote(self.DB_USER or "", safe="")
        password = quote(self.DB_PASS or "", safe="")
        return unquote(f"postgresql+asyncpg://{user}:{password}@{self.DB_HOST}/{tenant_db}")

    def get_tenant_database_url_sync(self, tenant: str = "master") -> str:
        """Generate SYNC database URL for a specific tenant (psycopg2)"""
        tenant_db = self.get_tenant_database_name(tenant)
        user = quote(self.DB_USER or "", safe="")
        password = quote(self.DB_PASS or "", safe="")
        return unquote(f"postgresql+psycopg2://{user}:{password}@{self.DB_HOST}/{tenant_db}")

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown fields instead of raising an error
    )


settings = ProjectSettings()

# === File Storage Settings ===

class FileStorageSettings(BaseSettings):
    DEFAULT_STORAGE_PROVIDER: str = "local"

    AZURE_CONNECTION_STRING: Optional[str] = None
    AZURE_ACCOUNT_NAME: Optional[str] = None
    AZURE_ACCOUNT_KEY: Optional[str] = None
    AZURE_CONTAINER_NAME: Optional[str] = None

    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GOOGLE_STORAGE_BUCKET: Optional[str] = None

    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_STORAGE_BUCKET: Optional[str] = None
    AWS_REGION: Optional[str] = None
    AWS_S3_ENDPOINT_URL: Optional[str] = None
    AWS_BUCKET_NAME: Optional[str] = None

    GCP_PROJECT_ID: Optional[str] = None
    GCP_REGION: Optional[str] = None

    APP_URL: Optional[str] = "http://localhost:8000"


    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown fields instead of raising an error
    )

file_storage_settings = FileStorageSettings()