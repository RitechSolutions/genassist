import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from fastapi import UploadFile
from injector import inject
from openai import AsyncOpenAI
from sqlalchemy import UUID

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.date_time_utils import utc_now
from app.core.utils.enums.open_ai_fine_tuning_enum import FileStatus, JobStatus
from app.db.models import FineTuningJobModel
from app.repositories.openai_fine_tuning import FineTuningRepository
from app.schemas.open_ai_fine_tuning import CreateFineTuningJobRequest
from app.services.fine_tuning_event import FineTuningEventService


logger = logging.getLogger(__name__)


@inject
class OpenAIFineTuningService:
    def __init__(self, repository: FineTuningRepository, event_service: FineTuningEventService):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.repository = repository
        self.event_service = event_service


    async def upload_file(
            self,
            file: UploadFile,
            purpose: str,
            ):
        """
        Upload a file to OpenAI's API and store record in database.

        Args:
            file: The uploaded file
            purpose: Purpose of the file (e.g., "fine-tune", "assistants")

        Returns:
            OpenAI file upload response
        """
        try:
            # Read file content
            file_content = await file.read()

            # Reset file pointer for potential reuse
            await file.seek(0)

            # Upload to OpenAI
            logger.info(f"Uploading file {file.filename} ({len(file_content)} bytes) to OpenAI")

            response = await self.client.files.create(
                    file=(file.filename, file_content),
                    purpose=purpose
                    )

            logger.info(f"Successfully uploaded file to OpenAI. File ID: {response.id}")

            # Store in database
            await self.repository.create_file_record(
                    openai_file_id=response.id,
                    filename=response.filename,
                    purpose=response.purpose,
                    bytes=response.bytes,
                    )

            return response

        except Exception as e:
            logger.error(f"Error uploading file to OpenAI: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_UPLOAD_FILE_OPEN_AI)


    async def create_fine_tuning_job(
            self,
            job_request: CreateFineTuningJobRequest,
            ):
        """
        Create a fine-tuning job in OpenAI and store record in database.

        Args:
            job_request: Fine-tuning job configuration

        Returns:
            OpenAI fine-tuning job response
        """
        try:
            # Verify training file exists in our DB
            training_file = await self.repository.get_file_by_openai_id(job_request.training_file)
            if not training_file:
                logger.error(f"Training file {job_request.training_file} not found in database")
                raise AppException(
                        error_key=ErrorKey.ERROR_CREATE_JOB_OPEN_AI
                        )

            # Verify validation file if provided
            validation_file = None
            if job_request.validation_file:
                validation_file = await self.repository.get_file_by_openai_id(job_request.validation_file)
                if not validation_file:
                    logger.error(f"Validation file {job_request.validation_file} not found in database")
                    raise AppException(
                            error_key=ErrorKey.ERROR_CREATE_JOB_OPEN_AI
                            )

            logger.info(f"Creating fine-tuning job with training_file: {job_request.training_file}")

            # Prepare the request parameters
            params = {
                "training_file": job_request.training_file,
                "model": job_request.model
                }

            # Add optional parameters if provided
            if job_request.validation_file:
                params["validation_file"] = job_request.validation_file
            if job_request.hyperparameters:
                params["hyperparameters"] = job_request.hyperparameters
            if job_request.suffix:
                params["suffix"] = job_request.suffix

            # Create fine-tuning job in OpenAI
            response = await self.client.fine_tuning.jobs.create(**params)

            logger.info(f"Successfully created fine-tuning job. Job ID: {response.id}")

            # Store in database
            job = await self.repository.create_job_record(
                    openai_job_id=response.id,
                    training_file_id=training_file.id,
                    validation_file_id=validation_file.id if validation_file else None,
                    model=response.model,
                    status=JobStatus(response.status),
                    hyperparameters=job_request.hyperparameters,
                    suffix=job_request.suffix,
                    )

            return job

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error creating fine-tuning job: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_CREATE_JOB_OPEN_AI)


    async def get_fine_tuning_job(self, job_id: UUID, sync: bool = False):
        """
        Retrieve a fine-tuning job by ID with events and progress.

        Args:
            job_id: The fine-tuning job ID
            sync: Whether to sync with OpenAI API (syncs both job status and events)

        Returns:
            Job details with events and progress information
        """
        try:
            logger.info(f"Fetching fine-tuning job: {job_id}")

            # Get job from database
            job_record = await self.repository.get_by_id(job_id, eager=["training_file", "validation_file", "events"])
            if not job_record:
                raise AppException(error_key=ErrorKey.ERROR_EXIST_JOB_OPEN_AI)

            # Determine if we should sync with OpenAI
            should_sync = sync or job_record.status in [
                JobStatus.VALIDATING_FILES,
                JobStatus.QUEUED,
                JobStatus.RUNNING
                ]

            if should_sync:
                # Fetch fresh data from OpenAI
                logger.info(f"Syncing job {job_id} with OpenAI API")
                response = await self.client.fine_tuning.jobs.retrieve(job_record.openai_job_id)

                # Update database with fresh data
                job_record = await self.repository.update_job_status(
                        id=job_record.id,
                        status=JobStatus(response.status),
                        fine_tuned_model=response.fine_tuned_model,
                        finished_at=datetime.fromtimestamp(response.finished_at) if response.finished_at else None,
                        trained_tokens=response.trained_tokens,
                        error_message=response.error.message if response.error else None,
                        error_code=response.error.code if response.error else None
                        )

                # Sync events for active jobs
                if sync or job_record.status in [JobStatus.VALIDATING_FILES, JobStatus.QUEUED, JobStatus.RUNNING]:
                    try:

                        await self.event_service.sync_events_for_job(job_record.id)
                        logger.info(f"Synced events for job {job_id}")

                        # Refresh to get updated events
                        await self.repository.db.refresh(job_record)
                    except Exception as event_error:
                        logger.error(f"Error syncing events for job {job_id}: {str(event_error)}")

                logger.info(f"Retrieved and synced job {job_id}. Status: {response.status}")
            else:
                # Job is in terminal state, return cached data but still fetch from OpenAI for consistency
                logger.info(f"Job {job_id} is in terminal state ({job_record.status}), fetching from OpenAI")
                response = await self.client.fine_tuning.jobs.retrieve(job_record.openai_job_id)
                logger.info(f"Successfully retrieved job {job_id}. Status: {response.status}")

            # Build response with events and progress
            job_dict = job_record.to_dict()

            # Add events
            self.attach_job_events(job_dict, job_record)

            # Add progress information
            try:
                progress = await self.event_service.get_job_progress(job_record.id)
                job_dict['progress'] = progress
            except Exception as progress_error:
                logger.error(f"Error getting progress for job {job_id}: {str(progress_error)}")
                job_dict['progress'] = None

            return job_dict

        except Exception as e:
            logger.error(f"Error retrieving fine-tuning job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_MONITOR_JOB_OPEN_AI)


    def attach_job_events(self, job_dict: dict[Any, Any], job_record: FineTuningJobModel):
        job_dict['events'] = [
            {
                "id": str(event.id),
                "openai_event_id": event.openai_event_id,
                "level": event.level,
                "message": event.message,
                "event_created_at": event.event_created_at.isoformat(),
                "metrics": event.metrics,
                "created_at": event.created_at.isoformat()
                }
            for event in job_record.events
            ]


    async def get_all_by_statuses(self, statuses: Optional[list[JobStatus]] = None) -> list[FineTuningJobModel]:
        return await self.repository.get_jobs_by_status(statuses)

    async def get_jobs(
            self,
            status: Optional[JobStatus] = None,
            sync: bool = False
            ):
        """
        List all fine-tuning jobs for a user.

        Args:
            status: Optional status filter
            sync: Whether to sync with OpenAI API (syncs both job status and events)

        Returns:
            List of job records with progress information
        """
        try:
            logger.info(f"Listing jobs, status: {status}, sync: {sync}")
            jobs = await self.repository.list_jobs(status=status)
            logger.info(f"Found {len(jobs)} jobs")

            if sync and jobs:
                logger.info(f"Syncing {len(jobs)} jobs with OpenAI API")

                synced_jobs = []

                for job in jobs:
                    try:
                        # Sync job status
                        response = await self.client.fine_tuning.jobs.retrieve(job.openai_job_id)
                        updated_job = await self.repository.update_job_status(
                                job.id,
                                status=JobStatus(response.status),
                                fine_tuned_model=response.fine_tuned_model,
                                finished_at=datetime.fromtimestamp(
                                        response.finished_at) if response.finished_at else None,
                                trained_tokens=response.trained_tokens,
                                error_message=response.error.message if response.error else None,
                                error_code=response.error.code if response.error else None
                                )
                        synced_jobs.append(updated_job)

                        # Sync events for active jobs
                        if sync or updated_job.status in [JobStatus.VALIDATING_FILES, JobStatus.QUEUED,
                                JobStatus.RUNNING]:
                            try:
                                await self.event_service.sync_events_for_job(updated_job.id)
                            except Exception as event_error:
                                logger.error(f"Error syncing events for job {updated_job.id}: {str(event_error)}")

                        await asyncio.sleep(0.2)

                    except Exception as e:
                        logger.error(f"Error syncing job {job.openai_job_id}: {str(e)}")
                        synced_jobs.append(job)

                jobs = synced_jobs
                logger.info(f"Successfully synced {len(synced_jobs)} jobs")

            jobs_with_progress = []
            for job in jobs:
                job_dict = job.to_dict()
                self.attach_job_events(job_dict, job)
                try:
                    progress = await self.event_service.get_job_progress(job.id)
                    job_dict['progress'] = progress
                except Exception as e:
                    logger.error(f"Error getting progress for job {job.id}: {str(e)}")
                    job_dict['progress'] = None
                jobs_with_progress.append(job_dict)

            return jobs_with_progress

        except Exception as e:
            logger.error(f"Error listing jobs: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_MONITOR_JOB_OPEN_AI)


    async def get_files(self, sync: bool = False):
        """
        List all uploaded files.

        Args:
            sync: Whether to sync with OpenAI API for latest file statuses

        Returns:
            List of file records from database
        """
        try:
            logger.info(f"Listing files, sync: {sync}")

            if sync:
                # Fetch all files from OpenAI
                logger.info("Fetching all files from OpenAI API")
                openai_response = await self.client.files.list()
                openai_files = {file.id: file for file in openai_response.data}
                logger.info(f"Found {len(openai_files)} files in OpenAI")

                # Get files from database
                db_files = await self.repository.list_files_by_user()
                db_files_dict = {file.openai_file_id: file for file in db_files}

                synced_count = 0
                added_count = 0
                deleted_count = 0

                # Update existing files in database
                for file_record in db_files:
                    if file_record.openai_file_id in openai_files:
                        # File exists in OpenAI, update it
                        openai_file = openai_files[file_record.openai_file_id]
                        file_record.status = openai_file.status if hasattr(openai_file,
                                                                           'status') else FileStatus.UPLOADED
                        file_record.bytes = openai_file.bytes
                        file_record.filename = openai_file.filename
                        synced_count += 1
                    else:
                        # File not found in OpenAI, mark as deleted
                        logger.warning(f"File {file_record.openai_file_id} not found in OpenAI")
                        file_record.status = FileStatus.DELETED
                        deleted_count += 1

                # Optional: Add files from OpenAI that aren't in database
                for openai_file_id, openai_file in openai_files.items():
                    if openai_file_id not in db_files_dict:
                        logger.info(f"Found file {openai_file_id} in OpenAI but not in database, adding it")
                        new_file = await self.repository.create_file_record(
                                openai_file_id=openai_file.id,
                                filename=openai_file.filename,
                                purpose=openai_file.purpose,
                                bytes=openai_file.bytes,
                                )
                        db_files.append(new_file)
                        added_count += 1

                await self.repository.db.commit()
                logger.info(
                        f"Sync complete: {synced_count} updated, {added_count} added, {deleted_count} deleted"
                        )

                # Return fresh list
                return await self.repository.list_files_by_user()
            else:
                # No sync, just return database records
                files = await self.repository.list_files_by_user()
                logger.info(f"Found {len(files)} files in database")
                return files

        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_FETCH_FILES_OPEN_AI)


    async def cancel_fine_tuning_job(self, job_id: UUID):
        """
        Cancel a fine-tuning job.

        Args:
            job_id: The fine-tuning job ID (OpenAI format: ftjob-xxx)

        Returns:
            Updated job record from database
        """
        try:
            logger.info(f"Cancelling fine-tuning job: {job_id}")
            job_record = await self.repository.get_job_by_id(job_id)
            if not job_record:
                raise AppException(ErrorKey.ERROR_JOB_NOT_FOUND)

            # Cancel in OpenAI
            await self.client.fine_tuning.jobs.cancel(job_record.openai_job_id)

            updated_job = await self.repository.update_job_status(
                    job_record.id,
                    status=JobStatus.CANCELLED,
                    finished_at=utc_now(),
                    error_message="Job cancelled by user"
                    )
            logger.info(f"Updated job {job_id} status to CANCELLED in database")
            return updated_job

        except Exception as e:
            logger.error(f"Error cancelling fine-tuning job {job_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_CANCEL_JOB_OPEN_AI)


    async def delete_file(self, file_id: str):
        """
        Delete a file from OpenAI and update database.

        Args:
            file_id: The OpenAI file ID (format: file-xxx)

        Returns:
            Deletion confirmation
        """
        try:
            logger.info(f"Deleting file: {file_id}")

            # Get file from database first
            file_record = await self.repository.get_file_by_openai_id(file_id)
            if not file_record:
                logger.warning(f"File {file_id} not found in database")
                raise AppException(
                        error_key=ErrorKey.ERROR_DELETE_FILE_JOB_PROG_OPEN_AI,
                        )

            # Check if file is being used in any active jobs
            active_jobs = await self.repository.get_active_jobs()
            for job in active_jobs:
                if job.training_file_id == file_record.id or job.validation_file_id == file_record.id:
                    logger.error(f"File {file_id} is being used in active job {job.openai_job_id}")
                    raise AppException(
                            error_key=ErrorKey.ERROR_DELETE_FILE_JOB_PROG_OPEN_AI,
                            )

            # Delete from OpenAI
            await self.client.files.delete(file_id)

            logger.info(f"Successfully deleted file {file_id} from OpenAI")

            # Update status in database (or delete the record)
            file_record.status = "DELETED"
            await self.repository.db.commit()
            await self.repository.db.refresh(file_record)

            logger.info(f"Updated file {file_id} status to DELETED in database")

            return {
                "id": file_id,
                "object": "file",
                "deleted": True
                }

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_DELETE_FILE_OPEN_AI)


    def get_fine_tunable_models(self):
        """
        Get list of models that support fine-tuning.
        This is hardcoded based on OpenAI documentation.
        Check https://platform.openai.com/docs/guides/fine-tuning for latest updates.

        Returns:
            List of fine-tunable model names
        """
        # Updated as of October 2024
        fine_tunable_models = [
            "gpt-4o-2024-08-06",
            "gpt-4o-mini-2024-07-18",
            "gpt-4-0613",
            "gpt-3.5-turbo-0125",
            "gpt-3.5-turbo-1106",
            "gpt-3.5-turbo-0613",
            ]

        logger.info(f"Returning {len(fine_tunable_models)} fine-tunable models")
        return fine_tunable_models


    async def delete_fine_tuned_model(self, model_id: str):
        """
        Delete a fine-tuned model from OpenAI.
        Args:
            model_id: The fine-tuned model ID (format: ft:gpt-4o-mini:org:suffix:abc123)

        Returns:
            Deletion confirmation
        """
        try:
            # Validate it's a fine-tuned model
            if not model_id.startswith('ft'):
                logger.error(f"Attempted to delete non-fine-tuned model: {model_id}")
                raise AppException(
                        error_key=ErrorKey.ERROR_NON_FINE_TUNED,
                        )

            logger.info(f"Deleting fine-tuned model: {model_id}")

            # Delete from OpenAI
            _ = await self.client.models.delete(model_id)

            logger.info(f"Successfully deleted model {model_id} from OpenAI")

            # Update database - find the job that created this model
            try:
                job = await self.repository.get_job_by_fine_tuned_model(model_id)  # Singular

                if job:
                    await self.repository.soft_delete(job)
                    logger.info(f"Updated job {job.openai_job_id} that referenced deleted model {model_id}")
                else:
                    logger.info(f"No job found in database for model {model_id}")

            except Exception as db_error:
                logger.warning(f"Failed to update database after model deletion: {str(db_error)}")

            return {
                "id": model_id,
                "object": "model",
                "deleted": True
                }
        except Exception as e:
            logger.error(f"Error deleting fine-tuned model {model_id}: {str(e)}")
            raise AppException(error_key=ErrorKey.ERROR_DELETE_MODEL)