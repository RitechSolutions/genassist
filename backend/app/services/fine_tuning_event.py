import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from injector import inject
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus
from app.db.models.fine_tuning import FineTuningEventModel
from app.repositories.fine_tuning_event import FineTuningEventRepository
from app.repositories.openai_fine_tuning import FineTuningRepository
from openai import AsyncOpenAI
from app.core.config.settings import settings


logger = logging.getLogger(__name__)


@inject
class FineTuningEventService:
    def __init__(
            self,
            event_repository: FineTuningEventRepository,
            job_repository: FineTuningRepository
            ):
        self.event_repository = event_repository
        self.job_repository = job_repository
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


    async def get_events_by_job_id(
            self,
            job_id: UUID,
            limit: Optional[int] = None,
            sync: bool = False
            ) -> List[FineTuningEventModel]:
        """
        Get events for a specific job.

        Args:
            job_id: Job UUID
            limit: Maximum number of events to return
            sync: Whether to sync with OpenAI first

        Returns:
            List of event records
        """
        try:
            # Verify job exists
            job = await self.job_repository.get_job_by_id(job_id)
            if not job:
                raise AppException(error_key=ErrorKey.ERROR_JOB_NOT_FOUND)

            # Sync with OpenAI if requested
            if sync:
                await self.sync_events_for_job(job_id)

            # Get events from database
            events = await self.event_repository.get_events_by_job_id(
                    job_id=job_id,
                    limit=limit,
                    order_desc=True
                    )

            logger.info(f"Retrieved {len(events)} events for job {job_id}")
            return events

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error getting events for job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_JOB_EVENT_BY_ID)


    async def sync_events_for_job(self, job_id: UUID) -> int:
        """
        Sync events from OpenAI for a specific job.
        Only fetches new events that don't exist locally.

        Args:
            job_id: Job UUID

        Returns:
            Number of new events added
        """
        try:
            # Get job from database
            job = await self.job_repository.get_job_by_id(job_id)
            if not job:
                raise AppException(error_key=ErrorKey.ERROR_JOB_NOT_FOUND)

            logger.info(f"Syncing events for job {job_id} (OpenAI ID: {job.openai_job_id})")

            # Fetch events from OpenAI (get all, limited to 1000 by OpenAI)
            openai_events = await self.client.fine_tuning.jobs.list_events(
                    fine_tuning_job_id=job.openai_job_id,
                    limit=1000
                    )

            logger.info(f"Fetched {len(openai_events.data)} events from OpenAI")

            # Filter out events that already exist
            new_events = []
            for openai_event in openai_events.data:
                exists = await self.event_repository.event_exists(openai_event.id)
                if not exists:
                    # Create event model
                    event = FineTuningEventModel(
                            job_id=job_id,
                            openai_event_id=openai_event.id,
                            level=openai_event.level,
                            message=openai_event.message,
                            event_created_at=datetime.fromtimestamp(openai_event.created_at),
                            metrics=openai_event.data if hasattr(openai_event, 'data') and openai_event.data else None
                            )
                    new_events.append(event)

            # Bulk create new events
            if new_events:
                await self.event_repository.bulk_create_events(new_events)
                logger.info(f"Added {len(new_events)} new events for job {job_id}")
            else:
                logger.info(f"No new events to add for job {job_id}")

            return len(new_events)

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error syncing events for job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_JOB_OPEN_AI_EVENT)


    async def sync_events_for_active_jobs(self) -> dict:
        """
        Sync events for all jobs that are currently in progress.

        Returns:
            Summary of sync results
        """
        try:
            logger.info("Syncing events for all active jobs")

            # Get all active jobs (in progress)
            active_statuses = [
                JobStatus.VALIDATING_FILES,
                JobStatus.QUEUED,
                JobStatus.RUNNING
                ]

            summary = {
                "total_jobs_synced": 0,
                "total_new_events": 0,
                "errors": []
                }

            for status in active_statuses:
                jobs = await self.job_repository.list_jobs(status=status)

                for job in jobs:
                    try:
                        new_events_count = await self.sync_events_for_job(job.id)
                        summary["total_jobs_synced"] += 1
                        summary["total_new_events"] += new_events_count
                    except Exception as e:
                        logger.error(f"Error syncing events for job {job.id}: {str(e)}")
                        summary["errors"].append({
                            "job_id": str(job.id),
                            "error": str(e)
                            })

            logger.info(
                    f"Sync complete: {summary['total_jobs_synced']} jobs, "
                    f"{summary['total_new_events']} new events, "
                    f"{len(summary['errors'])} errors"
                    )

            return summary

        except Exception as e:
            logger.error(f"Error syncing events for active jobs: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_ACTIVE_JOB_EVENTS_SYNC)


    async def get_job_progress(self, job_id: UUID) -> dict:
        """
        Get current progress for a job based on stored events.

        Args:
            job_id: Job UUID

        Returns:
            Progress information
        """
        try:
            # Get job
            job = await self.job_repository.get_job_by_id(job_id)
            if not job:
                raise AppException(error_key=ErrorKey.ERROR_JOB_NOT_FOUND)

            # If job is not active, return basic info
            if job.status not in [JobStatus.VALIDATING_FILES, JobStatus.QUEUED, JobStatus.RUNNING]:
                return {
                    "job_id": str(job_id),
                    "status": job.status.value,
                    "is_running": False,
                    "progress_percentage": 100 if job.status == JobStatus.SUCCEEDED else 0,
                    "message": f"Job is {job.status.value}"
                    }

            # Get latest event with metrics
            latest_event = await self.event_repository.get_latest_event_by_job_id(job_id)

            if not latest_event or not latest_event.metrics:
                return {
                    "job_id": str(job_id),
                    "status": job.status.value,
                    "is_running": True,
                    "message": "Waiting for training to start..."
                    }

            metrics = latest_event.metrics
            current_step = metrics.get('step')
            total_steps = metrics.get('total_steps')

            # Calculate progress
            progress_percentage = None
            if current_step and total_steps and total_steps > 0:
                progress_percentage = round((current_step / total_steps) * 100, 2)

            # Calculate estimated time remaining
            estimated_seconds_remaining = None
            estimated_finish_at = None

            if current_step and total_steps and current_step > 0:
                created_at_timestamp = job.created_at.timestamp()
                current_timestamp = datetime.now().timestamp()
                time_elapsed = current_timestamp - created_at_timestamp

                time_per_step = time_elapsed / current_step
                steps_remaining = total_steps - current_step
                estimated_seconds_remaining = int(time_per_step * steps_remaining)
                estimated_finish_at = int(current_timestamp + estimated_seconds_remaining)

            return {
                "job_id": str(job_id),
                "status": job.status.value,
                "is_running": True,
                "current_step": current_step,
                "total_steps": total_steps,
                "progress_percentage": progress_percentage,
                "estimated_seconds_remaining": estimated_seconds_remaining,
                "estimated_finish_at": estimated_finish_at,
                "created_at": int(job.created_at.timestamp()),
                "latest_metrics": metrics,
                "message": f"Step {current_step}/{total_steps}" if current_step else "In progress..."
                }

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error getting progress for job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_JOB_EVENTS)