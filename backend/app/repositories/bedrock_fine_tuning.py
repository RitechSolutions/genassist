import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.date_time_utils import utc_now
from app.core.utils.enums.bedrock_fine_tuning_enum import (
    BedrockDeploymentStatus,
    BedrockJobStatus,
)
from app.db.models.fine_tuning import BedrockFineTuningJobModel
from app.repositories import DbRepository


logger = logging.getLogger(__name__)


@inject
class BedrockFineTuningRepository(DbRepository[BedrockFineTuningJobModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(BedrockFineTuningJobModel, db)

    async def create_job_record(
        self,
        job_arn: str,
        job_name: str,
        base_model_id: str,
        custom_model_name: str,
        region: str,
        training_data_s3_uri: str,
        status: BedrockJobStatus,
        validation_data_s3_uri: Optional[str] = None,
        output_s3_uri: Optional[str] = None,
        hyperparameters: Optional[dict] = None,
        suffix: Optional[str] = None,
    ) -> BedrockFineTuningJobModel:
        job_record = BedrockFineTuningJobModel(
            job_arn=job_arn,
            job_name=job_name,
            base_model_id=base_model_id,
            custom_model_name=custom_model_name,
            region=region,
            training_data_s3_uri=training_data_s3_uri,
            validation_data_s3_uri=validation_data_s3_uri,
            output_s3_uri=output_s3_uri,
            hyperparameters=hyperparameters,
            suffix=suffix,
            status=status,
            last_synced_at=utc_now(),
        )
        self.db.add(job_record)
        await self.db.commit()
        await self.db.refresh(job_record)
        logger.info(f"Created Bedrock fine-tuning job record for {job_arn}")
        return job_record

    async def get_job_by_id(self, job_id: UUID) -> Optional[BedrockFineTuningJobModel]:
        query = select(BedrockFineTuningJobModel).where(
            BedrockFineTuningJobModel.id == job_id
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_job_by_arn(self, job_arn: str) -> Optional[BedrockFineTuningJobModel]:
        query = select(BedrockFineTuningJobModel).where(
            BedrockFineTuningJobModel.job_arn == job_arn
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def update_job_status(
        self,
        id: UUID,
        status: BedrockJobStatus,
        custom_model_arn: Optional[str] = None,
        output_s3_uri: Optional[str] = None,
        finished_at: Optional[datetime] = None,
        trained_tokens: Optional[int] = None,
        metrics: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> BedrockFineTuningJobModel:
        job = await self.get_job_by_id(id)
        if not job:
            raise AppException(ErrorKey.ERROR_JOB_NOT_FOUND)

        job.status = status
        job.last_synced_at = utc_now()

        if custom_model_arn:
            job.custom_model_arn = custom_model_arn
        if output_s3_uri:
            job.output_s3_uri = output_s3_uri
        if finished_at:
            job.finished_at = finished_at
        if trained_tokens is not None:
            job.trained_tokens = trained_tokens
        if metrics is not None:
            job.metrics = metrics
        if error_message:
            job.error_message = error_message

        await self.db.commit()
        await self.db.refresh(job)
        logger.info(f"Updated Bedrock job {id} status to {status}")
        return job

    async def update_deployment(
        self,
        id: UUID,
        deployment_status: BedrockDeploymentStatus,
        deployment_arn: Optional[str] = None,
    ) -> BedrockFineTuningJobModel:
        job = await self.get_job_by_id(id)
        if not job:
            raise AppException(ErrorKey.ERROR_JOB_NOT_FOUND)

        job.deployment_status = deployment_status
        if deployment_arn:
            job.deployment_arn = deployment_arn

        await self.db.commit()
        await self.db.refresh(job)
        logger.info(f"Updated Bedrock job {id} deployment to {deployment_status}")
        return job

    async def list_jobs(
        self, status: Optional[BedrockJobStatus] = None
    ) -> List[BedrockFineTuningJobModel]:
        query = select(BedrockFineTuningJobModel)
        if status:
            query = query.where(BedrockFineTuningJobModel.status == status)
        query = query.order_by(BedrockFineTuningJobModel.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_active_jobs(self) -> List[BedrockFineTuningJobModel]:
        query = select(BedrockFineTuningJobModel).where(
            BedrockFineTuningJobModel.status.in_(
                [BedrockJobStatus.IN_PROGRESS, BedrockJobStatus.STOPPING]
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_jobs_by_status(
        self, statuses: Optional[list[BedrockJobStatus]] = None
    ) -> List[BedrockFineTuningJobModel]:
        query = select(BedrockFineTuningJobModel)
        if statuses:
            query = query.where(BedrockFineTuningJobModel.status.in_(statuses))
        result = await self.db.execute(query)
        return result.scalars().all()

    async def soft_delete(self, obj: BedrockFineTuningJobModel) -> None:
        await self.db.execute(
            update(obj.__class__)
            .where(BedrockFineTuningJobModel.id == obj.id)
            .values(is_deleted=True)
            .execution_options(synchronize_session="fetch")
        )
        await self.db.commit()
