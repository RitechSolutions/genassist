from uuid import UUID
from injector import inject
import logging
from typing import List, Optional
from croniter import croniter, CroniterBadCronError
from pydantic import ValidationError

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
from app.services.ml_models import (
    MLModelsService,
    STALE_CATEGORICAL_DEFAULT_WARNING_PREFIX,
    merge_model_inference_params,
)
from app.services.ml_model_manager import MLModelManager

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

        # The workflow must be live; the shared lock holds off a concurrent delete
        await self._lock_live_workflow(config_data.workflow_id)

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

    async def _lock_live_workflow(self, workflow_id: UUID) -> None:
        """404 unless the workflow exists and is not deleted.

        Takes a shared row lock until commit, so a version or agent delete
        cannot retire the workflow between this check and the config write.
        """
        if not await self.workflow_repository.lock_live_shared(
            workflow_id, visible_to_caller=True
        ):
            raise AppException(status_code=404, error_key=ErrorKey.WORKFLOW_NOT_FOUND)

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

        # Validate the workflow only when it changes, so resending the current
        # one (e.g. to clear the cron of a config on a deleted workflow) works
        if update_data.workflow_id and update_data.workflow_id != config.workflow_id:
            await self._lock_live_workflow(update_data.workflow_id)

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


# Model fields filled from the run's training output, by output key.
_RUN_OUTPUT_FIELD = {
    "pkl_file_id": "pkl_file_id",
    "target_variable": "target_column",
    "features": "feature_columns",
}


def _valid_target_transform(target_transform) -> bool:
    """Whether a run's target_transform can be merged into inference_params."""
    if target_transform is None:
        return True
    if not isinstance(target_transform, dict):
        return False
    baseline = target_transform.get("baselineColumn")
    if baseline is None:
        return True
    # An empty baseline means "none"; a blank one would be saved and rejected.
    return isinstance(baseline, str) and (not baseline or bool(baseline.strip()))


def _malformed_run_output(fields: list[str]) -> AppException:
    return AppException(
        error_key=ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE,
        error_detail=(
            f"This run's training output has unexpected values for {', '.join(fields)}, "
            "so its model file cannot safely replace the current one. Run the "
            "pipeline again, then promote the new run."
        ),
    )


@inject
class MLModelPipelineRunService:
    """Service for ML model pipeline run business logic."""

    def __init__(
        self,
        run_repository: MLModelPipelineRunRepository,
        config_repository: MLModelPipelineConfigRepository,
        model_repository: MLModelsRepository,
        model_service: MLModelsService,
        model_manager: MLModelManager,
        workflow_repository: WorkflowRepository,
    ):
        self.run_repository = run_repository
        self.config_repository = config_repository
        self.model_repository = model_repository
        self.model_service = model_service
        self.model_manager = model_manager
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
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)

        # Validate run exists and is completed
        run = await self.run_repository.get_by_id(run_id)
        if run.model_id != model_id:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)

        if run.status != PipelineRunStatusEnum.COMPLETED:
            raise AppException(
                error_key=ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE,
                error_detail="Only completed pipeline runs can be promoted.",
            )

        # Read execution_output while the session is still active, to avoid
        # lazy loading after it expires. Only a dict output can describe a
        # trained model; anything else (e.g. a chat workflow's reply text) is
        # treated as a run that produced no model file.
        raw_output = (
            run.execution_output.get("output")
            if isinstance(run.execution_output, dict)
            else None
        )
        execution_output = raw_output if isinstance(raw_output, dict) else {}
        model_file_path = execution_output.get("model_file_path")
        pkl_file_id = execution_output.get("pkl_file_id")
        produced_model_file = bool(model_file_path or pkl_file_id)

        if promote_data.update_model_file and model_file_path and not pkl_file_id:
            if "pkl_file_id" in execution_output:
                error_detail = (
                    "This run's trained model file was not uploaded to File Manager, "
                    "so it cannot safely replace the current model artifact. Run the "
                    "pipeline again, then promote the new run."
                )
            else:
                error_detail = (
                    "This pipeline run predates stored model file IDs and cannot "
                    "safely replace the model artifact. Run the pipeline again, "
                    "then promote the new run."
                )
            raise AppException(
                error_key=ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE,
                error_detail=error_detail,
            )

        from app.schemas.ml_model import MLModelUpdate

        # Build and validate the model file switch before anything changes,
        # so a malformed run is refused cleanly instead of failing halfway.
        model_updates = {}
        stale_default_warnings = []
        if promote_data.update_model_file and pkl_file_id:
            warnings = execution_output.get("warnings")
            stale_default_warnings = [
                warning
                for warning in (warnings if isinstance(warnings, list) else [])
                if isinstance(warning, str)
                and warning.startswith(STALE_CATEGORICAL_DEFAULT_WARNING_PREFIX)
            ]
            target_column = execution_output.get("target_column")
            feature_columns = execution_output.get("feature_columns")
            target_transform = execution_output.get("target_transform")
            model_updates["pkl_file_id"] = pkl_file_id
            if target_column:
                model_updates["target_variable"] = target_column
            if feature_columns:
                if not (
                    isinstance(feature_columns, list)
                    and all(isinstance(name, str) for name in feature_columns)
                ):
                    raise _malformed_run_output(["feature_columns"])
                if not _valid_target_transform(target_transform):
                    raise _malformed_run_output(["target_transform"])
                model_updates["features"] = feature_columns
                model_updates["inference_params"] = merge_model_inference_params(
                    model.inference_params,
                    feature_columns,
                    target_transform.get("baselineColumn") if target_transform else None,
                )
        try:
            model_update = MLModelUpdate(**model_updates)
        except ValidationError as e:
            fields = {err["loc"][0] for err in e.errors() if err["loc"]}
            run_fields = sorted(
                _RUN_OUTPUT_FIELD.get(field, str(field))
                for field in fields - {"inference_params"}
            )
            if "inference_params" in fields:
                # The run's baseline was checked above, so the bad value comes
                # from the model's saved settings, not from this run.
                detail = (
                    "This model's saved inference settings are not valid, so "
                    "the run's model file cannot be applied. Fix the model's "
                    "inference settings, then promote the run again."
                )
                if run_fields:
                    detail += (
                        " This run's training output also has unexpected values for "
                        f"{', '.join(run_fields)}."
                    )
                raise AppException(
                    error_key=ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE,
                    error_detail=detail,
                ) from e
            raise _malformed_run_output(run_fields or ["model fields"]) from e

        # Get the pipeline config used by this run
        config = await self.config_repository.get_by_id(run.pipeline_config_id)

        # Set this config as default
        await self.config_repository.unset_default_for_model(model_id)
        from app.schemas.ml_model_pipeline import MLModelPipelineConfigUpdate

        update_data = MLModelPipelineConfigUpdate(is_default=True)
        config = await self.config_repository.update(config.id, update_data)

        result = {
            "message": (
                "Pipeline run promoted successfully"
                if produced_model_file
                else "Pipeline run promoted successfully. The run produced no "
                "model file, so the model's file, features and metrics were not changed."
            ),
            "model_updated": False,
            "default_config_id": str(config.id),
        }

        if stale_default_warnings:
            result["warnings"] = stale_default_warnings

        promotes_run_file = "pkl_file_id" in model_updates
        # Metrics describe one model file, so they only follow the run when the
        # model ends up serving that run's file.
        run_file_is_current = bool(pkl_file_id) and str(model.pkl_file_id or "") == str(pkl_file_id)
        run_metrics = execution_output.get("metrics")
        training_metrics = None
        if (
            promote_data.update_metrics
            and isinstance(run_metrics, dict)
            and (promotes_run_file or run_file_is_current)
        ):
            training_metrics = run_metrics

        if model_updates or training_metrics is not None:
            try:
                # One update, so the file and its metrics change together. A new
                # file without metrics leaves the model with empty metrics.
                await self.model_service.update(
                    model_id,
                    model_update,
                    training_metrics=training_metrics,
                )
                if promotes_run_file:
                    self.model_manager.invalidate_model(model_id)
                result["model_updated"] = True
            except Exception as e:
                logger.warning(
                    f"Error promoting model fields for model {model_id}: {str(e)}"
                )
                raise

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
