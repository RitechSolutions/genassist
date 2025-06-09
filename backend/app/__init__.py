import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config.logging import init_logging
from app.api.v1.routes._routes import register_routers
from app.core.config.settings import settings
from app.core.exceptions.exception_handler import init_error_handlers
from app.db.session import get_db, run_db_init_actions
from app.modules.agents.llm.provider import LLMProvider
from app.services.agent_knowledge import KnowledgeBaseService  # Import all models
from app.cache.redis_cache import init_fastapi_cache_with_redis
from app.file_system.file_system import ensure_directories
from app.middlewares._middleware import build_middlewares
from app.modules.agents.registry import AgentRegistry
from app.modules.agents.data.datasource_service import AgentDataSourceService


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

    ensure_directories()
    validate_env()
    init_error_handlers(app)
    register_routers(app)


    return app


def validate_env():
    # TODO add all required variables
    if not os.getenv("DB_NAME"):
        raise RuntimeError("Missing required env var: DB_NAME")

def init_agents(db):
    AgentDataSourceService.get_instance()
    AgentRegistry.get_instance()
    KnowledgeBaseService.get_instance(db)
    LLMProvider.get_instance()
    
# --------------------------------------------------------------------------- #
# Lifespan handler                                                            #
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def _lifespan(app: FastAPI):
    """
    Startup / shutdown scaffold.
    Runs **before** the first request and **after** the last response.
    """
    logger.debug("Running lifespan startup tasks …")

    await run_db_init_actions()

    # Warm-up singletons
    async for db in get_db():
        init_agents(db)

    await init_fastapi_cache_with_redis(app, settings)

    try:
        yield
    finally:
        if hasattr(app.state, "redis"):
            await app.state.redis.aclose()
        logger.debug("Lifespan shutdown complete.")
