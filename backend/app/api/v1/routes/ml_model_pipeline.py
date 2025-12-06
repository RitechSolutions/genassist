from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from fastapi.responses import FileResponse
from fastapi_injector import Injected
from typing import Optional, List
import os
import logging

from app.auth.dependencies import auth, permissions
from app.schemas.ml_model_pipeline import (
    MLModelPipelineConfigCreate,
    MLModelPipelineConfigUpdate,
    MLModelPipelineConfigRead,
    MLModelPipelineRunCreate,
    MLModelPipelineRunRead,
    MLModelPipelineRunPromote,
    MLModelPipelineArtifactRead,
    PipelineRunStatus,
    PipelineRunPromoteResponse
)
from app.services.ml_model_pipeline import (
    MLModelPipelineConfigService,
    MLModelPipelineRunService,
    MLModelPipelineArtifactService
)
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Pipeline Configuration Endpoints ====================

@router.get(
    "/{model_id}/pipeline-configs",
    response_model=List[MLModelPipelineConfigRead],
    dependencies=[Depends(auth), Depends(permissions("read:ml_model"))]
)
async def get_pipeline_configs(
    model_id: UUID,
    service: MLModelPipelineConfigService = Injected(MLModelPipelineConfigService)
):
    """Get all pipeline configurations for a model."""
    try:
        return await service.get_by_model_id(model_id)
    except AppException as e:
        if e.error_key == ErrorKey.ML_MODEL_NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{model_id}/pipeline-configs/{config_id}",
    response_model=MLModelPipelineConfigRead,
    dependencies=[Depends(auth), Depends(permissions("read:ml_model"))]
)
async def get_pipeline_config(
    model_id: UUID,
    config_id: UUID,
    service: MLModelPipelineConfigService = Injected(MLModelPipelineConfigService)
):
    """Get a single pipeline configuration."""
    try:
        return await service.get_by_id(config_id)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{model_id}/pipeline-configs",
    response_model=MLModelPipelineConfigRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions("create:ml_model"))]
)
async def create_pipeline_config(
    model_id: UUID,
    config_data: MLModelPipelineConfigCreate,
    service: MLModelPipelineConfigService = Injected(MLModelPipelineConfigService)
):
    """Create a new pipeline configuration."""
    # Ensure model_id matches
    config_data.model_id = model_id
    
    try:
        return await service.create(config_data)
    except AppException as e:
        if e.error_key == ErrorKey.ML_MODEL_NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        if e.error_key == ErrorKey.INTERNAL_ERROR and "cron" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{model_id}/pipeline-configs/{config_id}",
    response_model=MLModelPipelineConfigRead,
    dependencies=[Depends(auth), Depends(permissions("update:ml_model"))]
)
async def update_pipeline_config(
    model_id: UUID,
    config_id: UUID,
    config_update: MLModelPipelineConfigUpdate,
    service: MLModelPipelineConfigService = Injected(MLModelPipelineConfigService)
):
    """Update a pipeline configuration."""
    try:
        return await service.update(model_id, config_id, config_update)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        if e.error_key == ErrorKey.INTERNAL_ERROR and "cron" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{model_id}/pipeline-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions("delete:ml_model"))]
)
async def delete_pipeline_config(
    model_id: UUID,
    config_id: UUID,
    service: MLModelPipelineConfigService = Injected(MLModelPipelineConfigService)
):
    """Delete a pipeline configuration."""
    try:
        await service.delete(model_id, config_id)
        return None
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Pipeline Run Endpoints ====================

@router.get(
    "/{model_id}/pipeline-runs",
    response_model=List[MLModelPipelineRunRead],
    dependencies=[Depends(auth), Depends(permissions("read:ml_model"))]
)
async def get_pipeline_runs(
    model_id: UUID,
    status: Optional[PipelineRunStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    service: MLModelPipelineRunService = Injected(MLModelPipelineRunService)
):
    """Get all pipeline runs for a model."""
    try:
        return await service.get_by_model_id(model_id, status=status, limit=limit, offset=offset)
    except AppException as e:
        if e.error_key == ErrorKey.ML_MODEL_NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{model_id}/pipeline-runs/{run_id}",
    response_model=MLModelPipelineRunRead,
    dependencies=[Depends(auth), Depends(permissions("read:ml_model"))]
)
async def get_pipeline_run(
    model_id: UUID,
    run_id: UUID,
    service: MLModelPipelineRunService = Injected(MLModelPipelineRunService)
):
    """Get a single pipeline run."""
    try:
        return await service.get_by_id(model_id, run_id)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{model_id}/pipeline-runs",
    response_model=MLModelPipelineRunRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions("create:ml_model"))]
)
async def create_pipeline_run(
    model_id: UUID,
    run_data: MLModelPipelineRunCreate,
    request: Request,
    service: MLModelPipelineRunService = Injected(MLModelPipelineRunService)
):
    """Create and execute a new pipeline run."""
    try:
        run = await service.create(model_id, run_data)
        
        # Queue async execution using Celery app from request
        try:
            celery_app = request.app.celery_app
            # Use send_task with the task name string (more reliable)
            result = celery_app.send_task(
                "execute_pipeline_run",
                args=[str(run.id)],
                queue=None  # Use default queue
            )
            logger.info(f"Queued pipeline run execution: {run.id}, task_id: {result.id}")
        except Exception as task_error:
            logger.error(f"Error queueing pipeline run task: {str(task_error)}", exc_info=True)
            # Fallback: try importing and calling directly
            try:
                from app.tasks.ml_model_pipeline_tasks import execute_pipeline_run_task
                execute_pipeline_run_task.delay(str(run.id))
                logger.info(f"Queued pipeline run execution (fallback): {run.id}")
            except Exception as fallback_error:
                logger.error(f"Error in fallback task queueing: {str(fallback_error)}", exc_info=True)
                # Don't fail the request, but log the error
                # The run is created, it just won't execute automatically
        
        return run
    except AppException as e:
        if e.error_key == ErrorKey.ML_MODEL_NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{model_id}/pipeline-runs/{run_id}/promote",
    response_model=PipelineRunPromoteResponse,
    dependencies=[Depends(auth), Depends(permissions("update:ml_model"))]
)
async def promote_pipeline_run(
    model_id: UUID,
    run_id: UUID,
    promote_data: MLModelPipelineRunPromote = MLModelPipelineRunPromote(),
    service: MLModelPipelineRunService = Injected(MLModelPipelineRunService)
):
    """Promote a completed pipeline run to update the model."""
    try:
        result = await service.promote_run(model_id, run_id, promote_data)
        return PipelineRunPromoteResponse(**result)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Pipeline Artifact Endpoints ====================

@router.get(
    "/{model_id}/pipeline-runs/{run_id}/artifacts",
    response_model=List[MLModelPipelineArtifactRead],
    dependencies=[Depends(auth), Depends(permissions("read:ml_model"))]
)
async def get_pipeline_artifacts(
    model_id: UUID,
    run_id: UUID,
    service: MLModelPipelineArtifactService = Injected(MLModelPipelineArtifactService)
):
    """Get all artifacts for a pipeline run."""
    try:
        return await service.get_by_run_id(model_id, run_id)
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{model_id}/pipeline-runs/{run_id}/artifacts/{artifact_id}/download",
    dependencies=[Depends(auth), Depends(permissions("read:ml_model"))]
)
async def download_artifact(
    model_id: UUID,
    run_id: UUID,
    artifact_id: UUID,
    service: MLModelPipelineArtifactService = Injected(MLModelPipelineArtifactService)
):
    """Download an artifact file."""
    try:
        artifact = await service.get_by_id(model_id, run_id, artifact_id)
        
        # Validate file exists
        if not os.path.exists(artifact.artifact_path):
            raise HTTPException(
                status_code=404,
                detail="Artifact file not found on disk"
            )
        
        # Determine media type based on artifact type
        media_type = "application/octet-stream"
        if artifact.artifact_type.value == "metrics":
            media_type = "application/json"
        elif artifact.artifact_type.value == "logs":
            media_type = "text/plain"
        
        return FileResponse(
            path=artifact.artifact_path,
            filename=artifact.artifact_name,
            media_type=media_type
        )
    except AppException as e:
        if e.error_key == ErrorKey.NOT_FOUND:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error downloading artifact: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading artifact: {str(e)}")

