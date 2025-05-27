from celery import Celery
from app.core.config.settings import settings
from celery.schedules import crontab

celery_app = Celery(
    "genassist",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.tasks", "app.tasks.s3_tasks"]
)

# Configure Celery
celery_app.conf.update(
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
)

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    "run-example-task": {
        "task": "app.tasks.tasks.example_periodic_task",
        # Run at the start of every 5th minute (0, 5, 10, 15, etc.)
        "schedule": crontab(minute="*/5"),
        "options": {
            "expires": 3600  # Task expires after 1 hour
        }
    },
    "cleanup-stale-conversations": {
        "task": "app.tasks.tasks.cleanup_stale_conversations",
        # Run at 2 minutes past every 5th minute (2, 7, 12, 17, etc.)
        "schedule": crontab(minute="2-59/5"),
        "options": {
            "expires": 3600  # Task expires after 1 hour
        }
    },
    # Optional: Add periodic S3 import task if needed
    # "import-s3-files": {
    #     "task": "app.tasks.s3_tasks.import_s3_files_to_kb",
    #     "schedule": crontab(hour="*/12"),  # Run every 12 hours
    #     "kwargs": {
    #         "prefix": "documents/",
    #         "file_extensions": [".pdf", ".txt"],
    #         "max_files": 100
    #     },
    #     "options": {
    #         "expires": 7200  # Task expires after 2 hours
    #     }
    # }
} 