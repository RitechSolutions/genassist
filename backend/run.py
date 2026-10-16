"""
This is the main file for the FastAPI application.
It is used to run the application in development mode.
"""
import os

# Prefer HF_HOME over deprecated TRANSFORMERS_CACHE (Transformers v5+).
# Must run before any code that imports transformers/sentence_transformers.
if "TRANSFORMERS_CACHE" in os.environ:
    if "HF_HOME" not in os.environ:
        os.environ["HF_HOME"] = os.environ["TRANSFORMERS_CACHE"]
    del os.environ["TRANSFORMERS_CACHE"]

import logging
import uvicorn

from app import create_app
from app.core.config.settings import settings
from migrations import run_migrations  # Import after logging is set up

logger = logging.getLogger(__name__)

# Create the FastAPI app (after logging is ready)
app = create_app()

if __name__ == "__main__":
    os.environ.setdefault("ALEMBIC_SKIP_FILECONFIG", "1")
    run_migrations(settings.DATABASE_URL_SYNC)

    # Run migrations for all active tenant databases
    from migrations import run_migrations_for_all_tenants
    run_migrations_for_all_tenants()

    port = int(os.environ.get("FASTAPI_RUN_PORT", 8000))
    debug_mode = os.environ.get("RELOAD", "False").lower() == "true"

    workers = int(os.environ.get("WORKERS", 1))
    # The app imports transformers/sentence-transformers via legra; each worker loads
    # that stack. Too many workers can cause OOM or child process crashes. Prefer
    # scaling via more replicas (containers/pods) with workers=1 or workers=2.
    if workers > 2:
        logger.warning(
            "WORKERS=%s is high; the app loads ML libs (transformers/sentence-transformers) "
            "in every worker. Prefer WORKERS=1 or 2 and scale with more replicas to avoid "
            "OOM or child process crashes.",
            workers,
        )
    workers = min(workers, 4)  # hard cap to avoid runaway worker counts

    logger.debug("SSK KEY path:"+os.environ.get("SSL_KEYFILE_PATH", ""))
    logger.debug("SSK CRT path:"+os.environ.get("SSL_CERTFILE_PATH", ""))

    dir_path = os.path.dirname(os.path.realpath(__file__))
    logger.debug("current dir path:"+dir_path)
    logger.debug("reload_includes:"+str(["*.py"]))
    logger.debug("reload_excludes:" +
                 str([dir_path+"/containers", dir_path+"/.git"]))
    logger.debug("reload_dirs:"+str([dir_path+"/app"]))

    # Start Uvicorn server
    uvicorn.run("run:app", host="0.0.0.0", port=port, reload=debug_mode,
                reload_includes=["*.py"],
                reload_excludes=["./containers", "./.git",
                                 "./.idea", "./logs", "./alembic"],
                reload_dirs=["./app"],
                ssl_keyfile=os.environ.get("SSL_KEYFILE_PATH", "") if os.environ.get(
                    "USE_SSL", "True").lower() == 'true' else None,
                ssl_certfile=os.environ.get("SSL_CERTFILE_PATH", "") if os.environ.get(
                    "USE_SSL", "True").lower() == 'true' else None,
                log_level=os.environ.get("LOG_LEVEL", "debug").lower(),
                log_config=None,  # Use default logging configuration
                workers=workers,
                access_log=os.environ.get(
                    "ACCESS_LOG", "False").lower() == "true",
                use_colors=os.environ.get(
                    "USE_COLORS", "True").lower() == "true",
                proxy_headers=os.environ.get(
                    "PROXY_HEADERS", "False").lower() == "true",
                )
