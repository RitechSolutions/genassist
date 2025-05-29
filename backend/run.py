import os

import uvicorn
import logging

from app import create_app
from app.core.config.settings import settings
from migrations import run_migrations  # Import after logging is set up

logger = logging.getLogger(__name__)

# Create the FastAPI app (after logging is ready)
app = create_app()

if __name__ == "__main__":

    run_migrations(settings.DATABASE_URL_SYNC)

    port = int(os.environ.get("FASTAPI_RUN_PORT", 8000))
    debug_mode = os.environ.get("FASTAPI_DEBUG", "False").lower() == "true"

    logger.debug("SSK KEY path:"+os.environ.get("SSL_KEYFILE_PATH", ""))
    logger.debug("SSK CRT path:"+os.environ.get("SSL_CERTFILE_PATH", ""))

    dir_path = os.path.dirname(os.path.realpath(__file__))
    logger.debug("current dir path:"+dir_path)
    logger.debug("reload_includes:"+str(["*.py"]))
    logger.debug("reload_excludes:"+str([dir_path+"/containers",dir_path+"/.git"]))
    logger.debug("reload_dirs:"+str([dir_path+"/app"]))
          
    # Start Uvicorn server
    uvicorn.run("run:app", host="0.0.0.0", port=port, reload=debug_mode,
                reload_includes=["*.py"],
                reload_excludes=["./containers","./.git", "./.idea", "./logs", "./alembic"],
                reload_dirs=["./app"],
<<<<<<< HEAD
                ssl_keyfile=os.environ.get("SSL_KEYFILE_PATH", ""),
                ssl_certfile=os.environ.get("SSL_CERTFILE_PATH", "")
=======
                ssl_keyfile=os.environ.get("SSL_KEYFILE_PATH", "") if os.environ.get("USE_SSL", "True").lower() == 'true' else None,
                ssl_certfile=os.environ.get("SSL_CERTFILE_PATH", "") if os.environ.get("USE_SSL", "True").lower() == 'true' else None,
                log_level=os.environ.get("LOG_LEVEL", "debug").lower(),
                log_config=None,  # Use default logging configuration
                workers=int(os.environ.get("WORKERS", 1)),
                access_log=os.environ.get("ACCESS_LOG", "False").lower() == "true",
                use_colors=os.environ.get("USE_COLORS", "True").lower() == "true",
                proxy_headers=os.environ.get("PROXY_HEADERS", "False").lower() == "true",
>>>>>>> development
                )
