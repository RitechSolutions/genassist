import os
import logging
from app import create_app
from app.core.config.settings import settings

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    
    # Pass all command line arguments to Celery
    sys.argv[0] = 'celery'  # Replace script name with 'celery'
    celery_main()
