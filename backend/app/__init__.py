import json
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_injector import InjectorMiddleware, RequestScopeOptions, attach_injector
from app.core.config.logging import init_logging
from app.api.v1.routes._routes import register_routers
from app.core.config.settings import settings
from app.core.exceptions.exception_handler import init_error_handlers
from app.dependencies.injector import injector
from app.cache.redis_cache import init_fastapi_cache_with_redis
from app.dependencies.tenant_dependencies import pre_wormup_tenant_singleton
from app.file_system.file_system import ensure_directories
from app.middlewares._middleware import build_middlewares
from app.middlewares.rate_limit_middleware import init_rate_limiter
from app.db.multi_tenant_session import multi_tenant_manager

from celery.schedules import crontab
from celery import Celery


init_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Application-factory entry-point.
    Only orchestration happens here – all heavy lifting lives in helpers.
    """
    app = FastAPI(
        lifespan=_lifespan,
        middleware=build_middlewares(),
    )

    app.celery_app = create_celery()  # new

    add_di_middleware(app)

    ensure_directories()
    validate_env()

    init_error_handlers(app)

    # Initialize rate limiting
    init_rate_limiter(app)

    # TODO: retest this
    # from fastapi.staticfiles import StaticFiles
    # app.mount("/docu", StaticFiles(directory="docs-site", html=True), name="docu")

    register_routers(app)

    return app


def add_di_middleware(app):
    app.add_middleware(InjectorMiddleware, injector=injector)
    # Enable cleanup - fastapi-injector will handle AsyncSession through context managers
    options = RequestScopeOptions(enable_cleanup=True)
    attach_injector(app, injector, options)


def validate_env():
    if not os.getenv("DB_NAME"):
        raise RuntimeError("Missing required env var: DB_NAME")


# --------------------------------------------------------------------------- #
# Lifespan handler helpers                                                    #
# --------------------------------------------------------------------------- #

async def _initialize_redis_services(app: FastAPI):
    """
    Initialize all Redis-related services.

    This includes:
    - RedisConnectionManager (connection pool for conversations/WebSockets)
    - FastAPI cache (with dedicated pool for binary data)

    Returns:
        RedisConnectionManager: The initialized singleton instance
    """
    from app.cache.redis_connection_manager import RedisConnectionManager

    logger.info("Initializing Redis services...")

    # Get DI singleton and initialize connection pool
    redis_manager = injector.get(RedisConnectionManager)
    await redis_manager.initialize()

    connection_info = await redis_manager.get_connection_info()
    logger.info(f"Redis connection manager initialized: {connection_info}")

    # Initialize FastAPI cache using consistent pool settings
    await init_fastapi_cache_with_redis(app, settings, redis_manager)

    logger.info("Redis services initialization complete")
    return redis_manager


async def _cleanup_redis_services(app: FastAPI):
    """
    Clean up all Redis-related services.

    This closes:
    - FastAPI cache Redis connection
    - RedisConnectionManager connection pool
    """
    from app.cache.redis_connection_manager import RedisConnectionManager

    logger.info("Cleaning up Redis services...")

    # Close FastAPI cache connection
    if hasattr(app.state, "redis"):
        try:
            await app.state.redis.aclose()
            logger.info("FastAPI cache Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing FastAPI cache Redis: {e}")

    # Close RedisConnectionManager pool
    try:
        manager = injector.get(RedisConnectionManager)
        await manager.close()
        logger.info("RedisConnectionManager closed")
    except Exception as e:
        logger.error(f"Error closing RedisConnectionManager: {e}")


async def _initialize_websocket_services():
    """
    Initialize WebSocket-related services.

    This includes:
    - SocketConnectionManager (WebSocket rooms and Redis Pub/Sub)
    """
    from app.modules.websockets.socket_connection_manager import SocketConnectionManager

    logger.info("Initializing WebSocket services...")

    try:
        # Get instance from DI (Redis dependency already injected)
        socket_manager = injector.get(SocketConnectionManager)

        # Initialize Redis Pub/Sub subscriber for cross-server broadcasting
        await socket_manager.initialize_redis_subscriber()
        logger.info("SocketConnectionManager initialized with Redis Pub/Sub")
    except Exception as e:
        logger.error(f"Failed to initialize SocketConnectionManager: {e}")
        raise


async def _cleanup_websocket_services():
    """
    Clean up WebSocket-related services.

    This includes:
    - Closing all WebSocket connections
    - Shutting down Redis Pub/Sub subscriber
    """
    from app.modules.websockets.socket_connection_manager import SocketConnectionManager

    logger.info("Cleaning up WebSocket services...")

    try:
        socket_manager = injector.get(SocketConnectionManager)
        await socket_manager.cleanup()
        logger.info("SocketConnectionManager cleanup complete")
    except Exception as e:
        logger.error(f"Error during SocketConnectionManager cleanup: {e}")


# --------------------------------------------------------------------------- #
# Lifespan handler                                                            #
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def _lifespan(app: FastAPI):
    """
    Startup / shutdown scaffold.
    Runs **before** the first request and **after** the last response.

    Manages initialization and cleanup of:
    - Redis services (connection manager, cache)
    - WebSocket services (connection manager, pub/sub)
    - Database services (multi-tenant sessions)
    - Application services (permissions, tenants)
    """
    logger.debug("Running lifespan startup tasks...")

    # Generate OpenAPI schema
    await output_open_api(app)

    # Initialize services in dependency order
    await _initialize_redis_services(app)
    await _initialize_websocket_services()

    # Initialize database and application services
    await multi_tenant_manager.initialize()
    await pre_wormup_tenant_singleton()

    from app.core.permissions import sync_permissions_on_startup
    await sync_permissions_on_startup()

    logger.info("Application startup complete")

    try:
        yield  # Application runs here
    finally:
        logger.info("Starting application shutdown...")

        # Clean up services in reverse dependency order
        await _cleanup_websocket_services()
        await _cleanup_redis_services(app)
        await multi_tenant_manager.close_all()

        logger.info("Application shutdown complete")


async def output_open_api(app):
    schema = app.openapi()
    Path("openapi.json").write_text(json.dumps(schema, indent=2))


def create_celery():
    """
    Create and configure the Celery application.
    """
    logger.debug("Creating new Celery app instance")
    logger.debug(f"Redis URL: {settings.REDIS_URL}")

    celery_app = Celery(
        "genassist_celery_tasks",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
        include=[
            "app.tasks.base",
            "app.tasks.s3_tasks",
            "app.tasks.conversations_tasks",
            "app.tasks.zendesk_tasks",
            "app.tasks.audio_tasks",
            "app.tasks.sharepoint_tasks",
            "app.tasks.fine_tune_job_sync_tasks",
            "app.tasks.share_folder_tasks",
            "app.tasks.ml_model_pipeline_tasks",
            "app.tasks.kb_batch_tasks",

        ],
    )

    # Configure Celery
    celery_app.conf.update(
        broker_url=settings.REDIS_URL,  # Explicitly set broker URL
        result_backend=settings.REDIS_URL,  # Explicitly set result backend
        broker_transport_options={
            "visibility_timeout": 3600,  # 1 hour
            "fanout_prefix": True,
            "fanout_patterns": True,
            "max_connections": 50,  # Limit broker connection pool
        },
        redis_max_connections=50,  # Limit result backend connection pool
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=300,  # 5 minutes
        task_soft_time_limit=240,  # 4 minutes (soft limit)
        worker_max_tasks_per_child=1000,
        worker_prefetch_multiplier=1,
        worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
        worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
    )

    # Configure periodic tasks
    celery_app.conf.beat_schedule = {
        "run-example-task": {
            "task": "app.tasks.base.example_periodic_task",
            # Run at the start of every 5th minute (0, 5, 10, 15, etc.)
            "schedule": crontab(minute="*/5"),
            "options": {"expires": 3600},  # Task expires after 1 hour
        },
        "cleanup-stale-conversations": {
            "task": "app.tasks.conversations_tasks.cleanup_stale_conversations",
            # Run at 2 minutes past every 5th minute (2, 7, 12, 17, etc.)
            "schedule": crontab(minute="2-59/5"),
            "options": {"expires": 3600},  # Task expires after 1 hour
        },
        "import-s3-files": {
            "task": "app.tasks.s3_tasks.import_s3_files_to_kb",
            "schedule": crontab(hour="*/1"),  # Run every 1 hours
            "options": {"expires": 3000},  # Task expires after 50mins
        },
        "transcribe-s3-files": {
            "task": "app.tasks.audio_tasks.transcribe_audio_files_from_s3",
            "schedule": crontab(hour="*/1"),  # Run every 1 hours
            "options": {"expires": 3000},  # Task expires after 50mins
        },
        "run-zendesk-analysis-every-hour": {
            "task": "app.tasks.zendesk_tasks.analyze_zendesk_tickets_task",
            # Run at the start of every hour
            "schedule": crontab(minute="0", hour="*"),
            "options": {
                "expires": 3600,  # Task expires after 1 hour
            },
        },
        "import-sharepoint-files-to-kb": {
            "task": "app.tasks.sharepoint_tasks.import_sharepoint_files_to_kb",
            "schedule": crontab(hour="*/1"),  # Run every 1 hours
            "options": {"expires": 3000},  # Task expires after 50mins
        },
        "transcribe-audio-files-from-smb": {
            "task": "app.tasks.share_folder_tasks.transcribe_audio_files_from_smb",
            "schedule": crontab(hour="*/1"),  # Run every 1 hours
            "options": {
                "expires": 3000,  # Task expires after 50mins
            },
        },
        # Sync active fine-tuning jobs every 2 minutes
        'sync-active-fine-tuning-jobs': {
            'task': 'app.tasks.fine_tune_job_sync_tasks.sync_active_fine_tuning_jobs',
            'schedule': 120.0,  # Every 2 minutes (120 seconds)
            },
        # Check for scheduled ML model pipeline runs every minute
        'check-scheduled-pipeline-runs': {
            'task': 'app.tasks.ml_model_pipeline_tasks.check_scheduled_pipeline_runs',
            'schedule': 60.0,  # Every minute (60 seconds)
            },
        

        
        # Sync active KB's jobs every 5 minutes
        'summarize-files-from-azure': {
            'task': 'app.tasks.kb_batch_tasks.batch_process_files_kb',
            'schedule': 300.0,  # Every 5 minutes (300 seconds)
            },

    }

    return celery_app
