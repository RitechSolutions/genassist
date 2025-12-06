import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.date_time_utils import utc_now
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus
from app.db.models.fine_tuning import FineTuningJobModel, OpenAIFileModel
from app.repositories import DbRepository


logger = logging.getLogger(__name__)


@inject
class FineTuningRepository(DbRepository[FineTuningJobModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(FineTuningJobModel, db)


    # ===== File Operations =====

    async def create_file_record(
            self,
            openai_file_id: str,
            filename: str,
            purpose: str,
            bytes: int,
            ) -> OpenAIFileModel:
        """Create a record of an uploaded file"""
        file_record = OpenAIFileModel(
                openai_file_id=openai_file_id,
                filename=filename,
                purpose=purpose,
                bytes=bytes,
                )
        self.db.add(file_record)
        await self.db.commit()
        await self.db.refresh(file_record)
        logger.info(f"Created file record for OpenAI file {openai_file_id}")
        return file_record


    async def get_file_by_openai_id(self, openai_file_id: str) -> Optional[OpenAIFileModel]:
        """Get file record by OpenAI file ID"""
        query = select(OpenAIFileModel).where(OpenAIFileModel.openai_file_id == openai_file_id)
        result = await self.db.execute(query)
        return result.scalars().first()


    async def list_files_by_user(
            self,
            ) -> List[OpenAIFileModel]:
        """List all files uploaded by a user"""
        query = select(OpenAIFileModel)
        query = query.order_by(OpenAIFileModel.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()


    # ===== Job Operations =====

    async def create_job_record(
            self,
            openai_job_id: str,
            training_file_id: UUID,
            model: str,
            status: JobStatus,
            validation_file_id: Optional[UUID] = None,
            hyperparameters: Optional[dict] = None,
            suffix: Optional[str] = None,
            ) -> FineTuningJobModel:
        """Create a record of a fine-tuning job"""
        job_record = FineTuningJobModel(
                openai_job_id=openai_job_id,
                training_file_id=training_file_id,
                validation_file_id=validation_file_id,
                model=model,
                hyperparameters=hyperparameters,
                suffix=suffix,
                status=status,
                last_synced_at=utc_now()
                )
        self.db.add(job_record)
        await self.db.commit()
        await self.db.refresh(job_record)
        logger.info(f"Created job record for OpenAI job {openai_job_id}")
        return job_record


    async def get_job_by_openai_id(self, openai_job_id: str) -> Optional[FineTuningJobModel]:
        """Get job record by OpenAI job ID with relationships"""
        query = select(FineTuningJobModel).where(
                FineTuningJobModel.openai_job_id == openai_job_id
                ).options(
                joinedload(FineTuningJobModel.training_file),
                joinedload(FineTuningJobModel.events)  # Add this
                )
        result = await self.db.execute(query)
        return result.scalars().first()


    async def get_job_by_id(self, job_id: UUID) -> Optional[FineTuningJobModel]:
        """Get job record by internal UUID"""
        query = select(FineTuningJobModel).where(
                FineTuningJobModel.id == job_id
                ).options(
                joinedload(FineTuningJobModel.training_file),
                joinedload(FineTuningJobModel.validation_file)
                )
        result = await self.db.execute(query)
        return result.scalars().first()


    async def update_job_status(
            self,
            id: UUID,
            status: JobStatus,
            fine_tuned_model: Optional[str] = None,
            finished_at: Optional[datetime] = None,
            trained_tokens: Optional[int] = None,
            error_message: Optional[str] = None,
            error_code: Optional[str] = None
            ) -> FineTuningJobModel:
        """Update job status from OpenAI sync"""
        job = await self.get_job_by_id(id)
        if not job:
            raise AppException(ErrorKey.ERROR_JOB_NOT_FOUND)

        job.status = status
        job.last_synced_at = utc_now()

        if fine_tuned_model:
            job.fine_tuned_model = fine_tuned_model
        if finished_at:
            job.finished_at = finished_at
        if trained_tokens:
            job.trained_tokens = trained_tokens
        if error_message:
            job.error_message = error_message
        if error_code:
            job.error_code = error_code

        await self.db.commit()
        await self.db.refresh(job)
        logger.info(f"Updated job {id} status to {status}")
        return job


    async def list_jobs(
            self,
            status: Optional[JobStatus] = None
            ) -> List[FineTuningJobModel]:
        """List all jobs created by a user"""
        query = select(FineTuningJobModel).options(
                joinedload(FineTuningJobModel.training_file),
                joinedload(FineTuningJobModel.validation_file),
                selectinload(FineTuningJobModel.events)
                )

        if status:
            query = query.where(FineTuningJobModel.status == status)

        query = query.order_by(FineTuningJobModel.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()


    async def get_active_jobs(self) -> List[FineTuningJobModel]:
        """Get all jobs that are not in a terminal state (for monitoring)"""
        query = select(FineTuningJobModel).where(
                FineTuningJobModel.status.in_([
                    JobStatus.VALIDATING_FILES,
                    JobStatus.QUEUED,
                    JobStatus.RUNNING
                    ])
                )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_jobs_by_status(self, statuses: Optional[list[JobStatus]] = None) -> List[FineTuningJobModel]:
        """Get all jobs that are not in a terminal state (for monitoring)"""
        query = (select(FineTuningJobModel))
        if statuses:
            query = query.where(
            FineTuningJobModel.status.in_(statuses)
            )
        result = await self.db.execute(query)
        return result.scalars().all()



    async def get_job_by_fine_tuned_model(self, fine_tuned_model: str) -> Optional[FineTuningJobModel]:
        """Get the job that produced a specific fine-tuned model"""
        query = select(FineTuningJobModel).where(
                FineTuningJobModel.fine_tuned_model == fine_tuned_model
                )
        result = await self.db.execute(query)
        job = result.scalars().first()

        # Sanity check - warn if there are duplicates
        all_results = result.scalars().all()
        if len(all_results) > 1:
            logger.warning(
                    f"Found {len(all_results)} jobs with same fine_tuned_model {fine_tuned_model}. "
                    "This indicates a database inconsistency."
                    )

        return job


    async def soft_delete(self, obj: FineTuningJobModel) -> None:
        await self.db.execute(
                update(obj.__class__)
                .where(FineTuningJobModel.id == obj.id)
                .values(is_deleted=True)
                .execution_options(synchronize_session="fetch")  # keep session in sync
                )
        await self.db.commit()
