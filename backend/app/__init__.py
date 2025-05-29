<<<<<<< HEAD
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config.logging import configure_logging
from app.core.config.settings import settings

from app.api.v1.routes import router

from dotenv import load_dotenv

from app.db.session import cold_start_db
from app.core.exceptions.exception_handler import init_error_handlers

from starlette.middleware import Middleware
from starlette_context.middleware import RawContextMiddleware

from app.middlewares.logger import log_request_info
import app.db.models
from app.modules.agents.registry import AgentRegistry  # Import all models
=======
from app.api.v1.routes import router
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config.logging import init_logging
from app.api.v1.routes._routes import register_routers
from app.core.config.settings import settings
from app.core.exceptions.exception_handler import init_error_handlers
from app.db.session import cold_start_db, get_db, run_db_init_actions
from app.modules.agents.llm.provider import LLMProvider
from app.repositories.llm_providers import LlmProviderRepository
from app.services.agent_knowledge import KnowledgeBaseService  # Import all models
from app.db.session import cold_start_db
from app.cache.redis_cache import init_fastapi_cache_with_redis
from app.file_system.file_system import ensure_directories
from app.middlewares._middleware import build_middlewares
from app.modules.agents.registry import AgentRegistry
from app.modules.agents.data.datasource_service import AgentDataSourceService
from app.services.llm_providers import LlmProviderService
>>>>>>> development


init_logging()
logger = logging.getLogger(__name__)


<<<<<<< HEAD
def create_app():

    app = FastAPI(lifespan=lifespan, middleware=[Middleware(RawContextMiddleware)])

    os.makedirs(settings.RECORDINGS_DIR, exist_ok=True)

=======
def create_app() -> FastAPI:
    """
    Application-factory entry-point.
    Only orchestration happens here – all heavy lifting lives in helpers.
    """
    app = FastAPI(
            lifespan=_lifespan,
            middleware=build_middlewares(),
            )
>>>>>>> development

    ensure_directories()
    validate_env()
    init_error_handlers(app)
    register_routers(app)

<<<<<<< HEAD
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080","http://localhost:8081","http://localhost:3000", "http://127.0.0.1:8080", "https://localhost:8080", "https://127.0.0.1:8080", "https://0.0.0.0:8080","https://genassist.ritech.io", "https://genassist-dev.ritech.io"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api", tags=["v1"])

    # Register request parameter logging
    app.middleware("http")(log_request_info)

    configure_logging()
=======
>>>>>>> development

    return app


<<<<<<< HEAD


def check_env_variables():
=======
def validate_env():
>>>>>>> development
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
<<<<<<< HEAD
async def lifespan(app: FastAPI):
    """
    Lifespan event for FastAPI to perform startup and shutdown tasks.
    """
    logger.debug("Running lifespan event...")
    AgentRegistry.get_instance()

    check_env_variables()
    if settings.CREATE_DB:
        await cold_start_db()
    yield
=======
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
>>>>>>> development
