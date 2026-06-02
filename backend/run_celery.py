import logging
import os
import threading
import time
from celery.signals import worker_process_init
from app import create_app
from app.core.config.settings import settings

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Path the liveness probe checks; interval the heartbeat thread refreshes it.
HEARTBEAT_FILE = os.environ.get("CELERY_HEARTBEAT_FILE", "/tmp/celery_heartbeat")
HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("CELERY_HEARTBEAT_INTERVAL", "15"))


def _start_heartbeat_thread() -> None:
    """
    Liveness heartbeat for the solo-pool worker.

    The solo pool runs tasks inline in the worker's main thread, so Celery's
    own control channel (``celery inspect ping``) cannot answer while a task is
    running — a healthy long task would look dead to an ``inspect ping`` probe.

    Instead we run a separate daemon thread that writes the current time to
    ``HEARTBEAT_FILE`` every ``HEARTBEAT_INTERVAL_SECONDS``. A k8s liveness
    probe checks that file's age (see deployment manifest). Because the task's
    async I/O releases the GIL while awaiting, this thread keeps ticking during
    a healthy long task, but stops if the process dies or hard-freezes — which
    is exactly what we want the probe to restart. (A task merely hung on the
    network is handled separately by the per-task asyncio.wait_for timeout.)
    """
    def _beat() -> None:
        while True:
            try:
                # Write+rename so the probe never reads a half-written file.
                tmp = f"{HEARTBEAT_FILE}.tmp"
                with open(tmp, "w") as fh:
                    fh.write(str(int(time.time())))
                os.replace(tmp, HEARTBEAT_FILE)
            except Exception as exc:  # never let the heartbeat thread die
                logger.warning("Celery heartbeat write failed: %s", exc)
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)

    thread = threading.Thread(target=_beat, name="celery-heartbeat", daemon=True)
    thread.start()
    logger.info(
        "Celery heartbeat thread started (file=%s, interval=%ss)",
        HEARTBEAT_FILE,
        HEARTBEAT_INTERVAL_SECONDS,
    )


@worker_process_init.connect
def init_worker_cache(**kwargs):
    from redis.asyncio import Redis as AsyncRedis
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.redis import RedisBackend
    redis = AsyncRedis.from_url(settings.REDIS_URL, decode_responses=False)
    FastAPICache.init(RedisBackend(redis), prefix="auth")
    logger.info("FastAPICache initialized for Celery worker process")


# Create the FastAPI app to get the Celery app instance
app = create_app()
celery_app = app.celery_app

if __name__ == "__main__":
    logger.debug(f"Starting Celery worker with Redis URL: {settings.REDIS_URL}")

    # You can run this script with different commands:
    # For worker: python run_celery.py worker -l DEBUG
    # For beat: python run_celery.py beat -l DEBUG
    # For flower: python run_celery.py flower -l DEBUG --port=5555

    # The command will be passed as arguments when running the script
    import sys
    from celery.__main__ import main as celery_main

    # Only the worker needs a liveness heartbeat (beat/flower are separate
    # processes with their own concerns). The solo pool runs the worker in this
    # main process, so a daemon thread here reflects worker liveness directly.
    if "worker" in sys.argv:
        _start_heartbeat_thread()

    # Pass all command line arguments to Celery
    sys.argv[0] = 'celery'  # Replace script name with 'celery'
    celery_main()
