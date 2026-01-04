from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime, timezone
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model_pipeline import (
    MLModelPipelineConfig,
    MLModelPipelineRun,
    MLModelPipelineArtifact,
    PipelineRunStatus,
    ArtifactType
)
from app.schemas.ml_model_pipeline import (
    MLModelPipelineConfigCreate,
    MLModelPipelineConfigUpdate,
    MLModelPipelineRunCreate,
    MLModelPipelineArtifactCreate
)
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError
import logging

logger = logging.getLogger(__name__)


@inject
class MLModelPipelineConfigRepository:
    """Repository for ML model pipeline configuration database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, config_data: MLModelPipelineConfigCreate) -> MLModelPipelineConfig:
        """Create a new pipeline configuration."""
        try:
            new_config = MLModelPipelineConfig(
                model_id=config_data.model_id,
                workflow_id=config_data.workflow_id,
                is_default=config_data.is_default,
                cron_schedule=config_data.cron_schedule,
            )
            self.db.add(new_config)
            await self.db.commit()
            await self.db.refresh(new_config)
            return new_config
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"IntegrityError while creating pipeline config: {str(e)}")
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR
            ) from e

    async def get_by_id(self, config_id: UUID) -> MLModelPipelineConfig:
        """Fetch pipeline configuration by ID."""
        query = (
            select(MLModelPipelineConfig)
            .options(selectinload(MLModelPipelineConfig.workflow))
            .where(
                MLModelPipelineConfig.id == config_id,
                MLModelPipelineConfig.is_deleted == 0
            )
        )
        result = await self.db.execute(query)
        config = result.scalars().first()

        if not config:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        return config

    async def get_by_model_id(self, model_id: UUID) -> List[MLModelPipelineConfig]:
        """Fetch all pipeline configurations for a model."""
        query = (
            select(MLModelPipelineConfig)
            .options(selectinload(MLModelPipelineConfig.workflow))
            .where(
                MLModelPipelineConfig.model_id == model_id,
                MLModelPipelineConfig.is_deleted == 0
            )
            .order_by(MLModelPipelineConfig.is_default.desc(), MLModelPipelineConfig.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_default_by_model_id(self, model_id: UUID) -> Optional[MLModelPipelineConfig]:
        """Get the default pipeline configuration for a model."""
        query = (
            select(MLModelPipelineConfig)
            .options(selectinload(MLModelPipelineConfig.workflow))
            .where(
                MLModelPipelineConfig.model_id == model_id,
                MLModelPipelineConfig.is_default.is_(True),
                MLModelPipelineConfig.is_deleted == 0
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def update(self, config_id: UUID, update_data: MLModelPipelineConfigUpdate) -> MLModelPipelineConfig:
        """Update an existing pipeline configuration."""
        config = await self.get_by_id(config_id)

        try:
            update_dict = update_data.model_dump(exclude_unset=True)
            for key, value in update_dict.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            try:
                config.updated_by = context.get("user_id")
            except (LookupError, ContextDoesNotExistError):
                # Context not available (e.g., in background tasks)
                pass

            await self.db.commit()
            await self.db.refresh(config)
            return config
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"IntegrityError while updating pipeline config: {str(e)}")
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR
            ) from e

    async def delete(self, config_id: UUID) -> MLModelPipelineConfig:
        """Soft delete a pipeline configuration."""
        config = await self.get_by_id(config_id)
        config.is_deleted = 1
        await self.db.commit()
        return config

    async def unset_default_for_model(self, model_id: UUID, exclude_config_id: Optional[UUID] = None):
        """Unset is_default for all configs of a model, optionally excluding one."""
        query = (
            select(MLModelPipelineConfig)
            .where(
                MLModelPipelineConfig.model_id == model_id,
                MLModelPipelineConfig.is_default.is_(True),
                MLModelPipelineConfig.is_deleted == 0
            )
        )
        if exclude_config_id:
            query = query.where(MLModelPipelineConfig.id != exclude_config_id)

        result = await self.db.execute(query)
        configs = result.scalars().all()
        for config in configs:
            config.is_default = False
        await self.db.commit()


@inject
class MLModelPipelineRunRepository:
    """Repository for ML model pipeline run database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, run_data: MLModelPipelineRunCreate) -> MLModelPipelineRun:
        """Create a new pipeline run."""
        try:
            new_run = MLModelPipelineRun(
                model_id=run_data.model_id,
                pipeline_config_id=run_data.pipeline_config_id,
                workflow_id=run_data.workflow_id,
                status=PipelineRunStatus.PENDING,
            )
            self.db.add(new_run)
            await self.db.commit()
            await self.db.refresh(new_run)
            return new_run
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"IntegrityError while creating pipeline run: {str(e)}")
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR
            ) from e

    async def get_by_id(self, run_id: UUID) -> MLModelPipelineRun:
        """Fetch pipeline run by ID."""
        query = (
            select(MLModelPipelineRun)
            .options(
                selectinload(MLModelPipelineRun.workflow),
                selectinload(MLModelPipelineRun.pipeline_config),
                selectinload(MLModelPipelineRun.artifacts)
            )
            .where(
                MLModelPipelineRun.id == run_id,
                MLModelPipelineRun.is_deleted == 0
            )
        )
        result = await self.db.execute(query)
        run = result.scalars().first()

        if not run:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        return run

    async def get_by_model_id(
        self,
        model_id: UUID,
        status: Optional[PipelineRunStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[MLModelPipelineRun]:
        """Fetch pipeline runs for a model with optional status filter."""
        query = (
            select(MLModelPipelineRun)
            .options(
                selectinload(MLModelPipelineRun.workflow),
                selectinload(MLModelPipelineRun.pipeline_config)
            )
            .where(
                MLModelPipelineRun.model_id == model_id,
                MLModelPipelineRun.is_deleted == 0
            )
        )
        if status:
            query = query.where(MLModelPipelineRun.status == status)

        query = query.order_by(MLModelPipelineRun.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        run_id: UUID,
        status: PipelineRunStatus,
        error_message: Optional[str] = None,
        execution_output: Optional[dict] = None,
        execution_id: Optional[UUID] = None
    ) -> MLModelPipelineRun:
        """Update pipeline run status and related fields."""
        run = await self.get_by_id(run_id)

        run.status = status

        if status == PipelineRunStatus.RUNNING and not run.started_at:
            run.started_at = datetime.now(timezone.utc)

        if status in [PipelineRunStatus.COMPLETED, PipelineRunStatus.FAILED, PipelineRunStatus.CANCELLED]:
            if not run.completed_at:
                run.completed_at = datetime.now(timezone.utc)

        if error_message:
            run.error_message = error_message

        if execution_output is not None:
            run.execution_output = execution_output

        if execution_id:
            run.execution_id = execution_id

        try:
            run.updated_by = context.get("user_id")
        except (LookupError, ContextDoesNotExistError):
            # Context not available (e.g., in background tasks)
            pass

        await self.db.commit()
        await self.db.refresh(run)
        return run


@inject
class MLModelPipelineArtifactRepository:
    """Repository for ML model pipeline artifact database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, artifact_data: MLModelPipelineArtifactCreate) -> MLModelPipelineArtifact:
        """Create a new pipeline artifact."""
        try:
            new_artifact = MLModelPipelineArtifact(
                pipeline_run_id=artifact_data.pipeline_run_id,
                artifact_type=ArtifactType(artifact_data.artifact_type.value),
                artifact_path=artifact_data.artifact_path,
                artifact_name=artifact_data.artifact_name,
                file_size=artifact_data.file_size,
            )
            self.db.add(new_artifact)
            await self.db.commit()
            await self.db.refresh(new_artifact)
            return new_artifact
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"IntegrityError while creating pipeline artifact: {str(e)}")
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR
            ) from e

    async def get_by_id(self, artifact_id: UUID) -> MLModelPipelineArtifact:
        """Fetch pipeline artifact by ID."""
        query = select(MLModelPipelineArtifact).where(
            MLModelPipelineArtifact.id == artifact_id,
            MLModelPipelineArtifact.is_deleted == 0
        )
        result = await self.db.execute(query)
        artifact = result.scalars().first()

        if not artifact:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        return artifact

    async def get_by_run_id(self, run_id: UUID) -> List[MLModelPipelineArtifact]:
        """Fetch all artifacts for a pipeline run."""
        query = (
            select(MLModelPipelineArtifact)
            .where(
                MLModelPipelineArtifact.pipeline_run_id == run_id,
                MLModelPipelineArtifact.is_deleted == 0
            )
            .order_by(MLModelPipelineArtifact.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

