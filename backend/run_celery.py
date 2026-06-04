import logging
from celery.signals import worker_process_init
from app import create_celery
from app.core.config.settings import settings

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@worker_process_init.connect
def init_worker_cache(**kwargs):
    from redis.asyncio import Redis as AsyncRedis
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.redis import RedisBackend
    redis = AsyncRedis.from_url(settings.REDIS_URL, decode_responses=False)
    FastAPICache.init(RedisBackend(redis), prefix="auth")
    logger.info("FastAPICache initialized for Celery worker process")


# Build the Celery app directly — NOT via create_app(). The worker never serves
# HTTP, and create_app() registers the FastAPI router graph, which transitively
# imports the workflow engine and pulls torch/sklearn into the process. Building the
# Celery app on its own keeps the (prefork) master process free of ML libs so it can
# fork children safely. See app/__init__.py create_celery() and the lean-import note.
celery_app = create_celery()

if __name__ == "__main__":
    logger.debug(f"Starting Celery worker with Redis URL: {settings.REDIS_URL}")

    # You can run this script with different commands:
    # For worker: python run_celery.py worker -l DEBUG
    # For beat: python run_celery.py beat -l DEBUG
    # For flower: python run_celery.py flower -l DEBUG --port=5555

    # The command will be passed as arguments when running the script
    import sys
    from celery.__main__ import main as celery_main

    # Pass all command line arguments to Celery
    sys.argv[0] = 'celery'  # Replace script name with 'celery'
    celery_main()
