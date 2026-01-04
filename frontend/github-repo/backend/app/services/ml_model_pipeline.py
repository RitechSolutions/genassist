from uuid import UUID
from injector import inject
import logging
from typing import List, Optional
from croniter import croniter, CroniterBadCronError

from app.repositories.ml_model_pipeline import (
    MLModelPipelineConfigRepository,
    MLModelPipelineRunRepository,
    MLModelPipelineArtifactRepository,
)
from app.repositories.ml_models import MLModelsRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.ml_model_pipeline import (
    MLModelPipelineConfigCreate,
    MLModelPipelineConfigUpdate,
    MLModelPipelineConfigRead,
    MLModelPipelineRunCreate,
    MLModelPipelineRunRead,
    MLModelPipelineRunPromote,
    PipelineRunStatus,
    MLModelPipelineArtifactRead,
)
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model_pipeline import PipelineRunStatus as PipelineRunStatusEnum

logger = logging.getLogger(__name__)


def validate_cron_expression(cron: Optional[str]) -> bool:
    """
    Validates cron expression format: * * * * *
    Returns True if valid, False otherwise
    """
    if cron is None or cron.strip() == "":
        return True  # None/empty is valid (no schedule)

    try:
        croniter.is_valid(cron.strip())
        return True
    except (CroniterBadCronError, ValueError):
        return False


@inject
class MLModelPipelineConfigService:
    """Service for ML model pipeline configuration business logic."""

    def __init__(
        self,
        config_repository: MLModelPipelineConfigRepository,
        model_repository: MLModelsRepository,
        workflow_repository: WorkflowRepository,
    ):
        self.config_repository = config_repository
        self.model_repository = model_repository
        self.workflow_repository = workflow_repository

    async def create(
        self, config_data: MLModelPipelineConfigCreate
    ) -> MLModelPipelineConfigRead:
        """Create a new pipeline configuration."""
        # Validate model exists
        await self.model_repository.get_by_id(config_data.model_id)

        # Validate workflow exists
        await self.workflow_repository.get_by_id(config_data.workflow_id)

        # Validate cron schedule if provided
        if config_data.cron_schedule and not validate_cron_expression(
            config_data.cron_schedule
        ):
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail="Invalid cron expression. Expected format: * * * * * (minute hour day month weekday)",
            )

        # If setting as default, unset other defaults for this model
        if config_data.is_default:
            await self.config_repository.unset_default_for_model(config_data.model_id)

        config = await self.config_repository.create(config_data)
        return MLModelPipelineConfigRead.model_validate(config)

    async def get_by_id(self, config_id: UUID) -> MLModelPipelineConfigRead:
        """Get pipeline configuration by ID."""
        config = await self.config_repository.get_by_id(config_id)
        return MLModelPipelineConfigRead.model_validate(config)

    async def get_by_model_id(self, model_id: UUID) -> List[MLModelPipelineConfigRead]:
        """Get all pipeline configurations for a model."""
        # Validate model exists
        await self.model_repository.get_by_id(model_id)

        configs = await self.config_repository.get_by_model_id(model_id)
        return [MLModelPipelineConfigRead.model_validate(config) for config in configs]

    async def update(
        self, model_id: UUID, config_id: UUID, update_data: MLModelPipelineConfigUpdate
    ) -> MLModelPipelineConfigRead:
        """Update a pipeline configuration."""
        # Validate model exists
        await self.model_repository.get_by_id(model_id)

        # Validate config belongs to model
        config = await self.config_repository.get_by_id(config_id)
        if config.model_id != model_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        # Validate workflow if provided
        if update_data.workflow_id:
            await self.workflow_repository.get_by_id(update_data.workflow_id)

        # Validate cron schedule if provided
        if update_data.cron_schedule is not None and not validate_cron_expression(
            update_data.cron_schedule
        ):
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail="Invalid cron expression. Expected format: * * * * * (minute hour day month weekday)",
            )

        # If setting as default, unset other defaults for this model
        if update_data.is_default:
            await self.config_repository.unset_default_for_model(
                model_id, exclude_config_id=config_id
            )

        updated_config = await self.config_repository.update(config_id, update_data)
        return MLModelPipelineConfigRead.model_validate(updated_config)

    async def delete(self, model_id: UUID, config_id: UUID):
        """Delete a pipeline configuration."""
        # Validate model exists
        await self.model_repository.get_by_id(model_id)

        # Validate config belongs to model
        config = await self.config_repository.get_by_id(config_id)
        if config.model_id != model_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        await self.config_repository.delete(config_id)


@inject
class MLModelPipelineRunService:
    """Service for ML model pipeline run business logic."""

    def __init__(
        self,
        run_repository: MLModelPipelineRunRepository,
        config_repository: MLModelPipelineConfigRepository,
        model_repository: MLModelsRepository,
        workflow_repository: WorkflowRepository,
    ):
        self.run_repository = run_repository
        self.config_repository = config_repository
        self.model_repository = model_repository
        self.workflow_repository = workflow_repository

    async def create(
        self, model_id: UUID, run_data: MLModelPipelineRunCreate
    ) -> MLModelPipelineRunRead:
        """Create a new pipeline run."""
        # Validate model exists
        await self.model_repository.get_by_id(model_id)

        # Validate config exists and belongs to model
        config = await self.config_repository.get_by_id(run_data.pipeline_config_id)
        if config.model_id != model_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        # Validate workflow exists
        await self.workflow_repository.get_by_id(run_data.workflow_id)

        # Ensure run_data has correct model_id
        run_data.model_id = model_id

        run = await self.run_repository.create(run_data)
        return MLModelPipelineRunRead.model_validate(run)

    async def get_by_id(self, model_id: UUID, run_id: UUID) -> MLModelPipelineRunRead:
        """Get pipeline run by ID."""
        # Validate model exists
        await self.model_repository.get_by_id(model_id)

        run = await self.run_repository.get_by_id(run_id)
        if run.model_id != model_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        return MLModelPipelineRunRead.model_validate(run)

    async def get_by_model_id(
        self,
        model_id: UUID,
        status: Optional[PipelineRunStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[MLModelPipelineRunRead]:
        """Get all pipeline runs for a model."""
        # Validate model exists
        await self.model_repository.get_by_id(model_id)

        status_enum = None
        if status:
            status_enum = PipelineRunStatusEnum(status.value)

        runs = await self.run_repository.get_by_model_id(
            model_id=model_id, status=status_enum, limit=limit, offset=offset
        )
        return [MLModelPipelineRunRead.model_validate(run) for run in runs]

    async def promote_run(
        self, model_id: UUID, run_id: UUID, promote_data: MLModelPipelineRunPromote
    ) -> dict:
        """Promote a completed pipeline run to update the model."""
        # Validate model exists
        model = await self.model_repository.get_by_id(model_id)
        if model is None:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        # Validate run exists and is completed
        run = await self.run_repository.get_by_id(run_id)
        if run.model_id != model_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        if run.status != PipelineRunStatusEnum.COMPLETED:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail="Only completed pipeline runs can be promoted",
            )

        # Get execution_output immediately while session is still active
        # This avoids lazy loading issues when the session expires
        execution_output = (
            run.execution_output.get("output", None) if run.execution_output else None
        )

        # Get the pipeline config used by this run
        config = await self.config_repository.get_by_id(run.pipeline_config_id)

        # Set this config as default
        await self.config_repository.unset_default_for_model(model_id)
        from app.schemas.ml_model_pipeline import MLModelPipelineConfigUpdate

        update_data = MLModelPipelineConfigUpdate(is_default=True)
        config = await self.config_repository.update(config.id, update_data)

        result = {
            "message": "Pipeline run promoted successfully",
            "model_updated": False,
            "default_config_id": str(config.id),
        }

        # Optionally update model file and metrics
        if promote_data.update_model_file and execution_output:
            model_file_path = execution_output.get("model_file_path")
            target_column = execution_output.get("target_column")
            feature_columns = execution_output.get("feature_columns")
            if model_file_path:
                from app.schemas.ml_model import MLModelUpdate

                try:
                    update_data = MLModelUpdate(
                        pkl_file=model_file_path,
                        target_variable=target_column,
                        features=feature_columns,
                    )
                    await self.model_repository.update(
                        model_id, update_data.model_dump(exclude_unset=True)
                    )
                    result["model_updated"] = True
                except Exception as e:
                    logger.warning(
                        f"Error updating pkl_file for model {model_id}: {str(e)}. "
                        "Attempting to update target and features fields."
                    )
                    raise e

        if promote_data.update_metrics and execution_output:
            # Update model metadata with metrics if needed
            # This could be extended to update inference_params or other fields
            pass

        return result


@inject
class MLModelPipelineArtifactService:
    """Service for ML model pipeline artifact business logic."""

    def __init__(
        self,
        artifact_repository: MLModelPipelineArtifactRepository,
        run_repository: MLModelPipelineRunRepository,
    ):
        self.artifact_repository = artifact_repository
        self.run_repository = run_repository

    async def get_by_run_id(
        self, model_id: UUID, run_id: UUID
    ) -> List[MLModelPipelineArtifactRead]:
        """Get all artifacts for a pipeline run."""
        # Validate run exists and belongs to model
        run = await self.run_repository.get_by_id(run_id)
        if run.model_id != model_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        artifacts = await self.artifact_repository.get_by_run_id(run_id)
        return [
            MLModelPipelineArtifactRead.model_validate(artifact)
            for artifact in artifacts
        ]

    async def get_by_id(
        self, model_id: UUID, run_id: UUID, artifact_id: UUID
    ) -> MLModelPipelineArtifactRead:
        """Get a single artifact by ID."""
        # Validate run exists and belongs to model
        run = await self.run_repository.get_by_id(run_id)
        if run.model_id != model_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        artifact = await self.artifact_repository.get_by_id(artifact_id)
        if artifact.pipeline_run_id != run_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND)

        return MLModelPipelineArtifactRead.model_validate(artifact)
