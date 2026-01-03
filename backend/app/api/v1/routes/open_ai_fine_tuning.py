import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, Query
from fastapi_injector import Injected
from app.auth.dependencies import auth, permissions
from app.auth.utils import get_current_user_id
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus
from app.schemas.open_ai_fine_tuning import (
    CreateFineTuningJobRequest,
    FineTuningJobResponse,
)
from app.schemas.user import UserUpdate
from app.services.open_ai_fine_tuning import OpenAIFineTuningService


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", dependencies=[
    Depends(auth),
    Depends(permissions("write:openai-file"))
])
async def upload_file_to_openai(
    file: UploadFile = File(...),
    purpose: str = Form(...),
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    Upload a file to OpenAI for fine-tuning or other purposes.
    """
    logger.info(f"User {get_current_user_id()} uploading file {file.filename} with purpose: {purpose}")
    return await service.upload_file(
        file=file,
        purpose=purpose,
    )


@router.post("/fine-tuning/jobs", dependencies=[
    Depends(auth),
    Depends(permissions("write:openai-job"))
])
async def create_fine_tuning_job(
    job_request: CreateFineTuningJobRequest,
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    Create a fine-tuning job in OpenAI.
    """
    logger.info(f"User {get_current_user_id()} creating fine-tuning job for file: {job_request.training_file}")
    job =  await service.create_fine_tuning_job(
        job_request=job_request,
    )
    return job


@router.get("/fine-tuning/jobs/{job_id}", dependencies=[
    Depends(auth),
    Depends(permissions("read:openai-job"))
])
async def get_fine_tuning_job(
    job_id: UUID,
    sync: bool = Query(True, description="Sync with OpenAI API for latest status"),
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    Retrieve the status and details of a fine-tuning job.
    Set sync=false to use cached data from database (faster but may be stale).
    """
    logger.info(f"Retrieving fine-tuning job: {job_id} (sync={sync})")
    return await service.get_fine_tuning_job(job_id, sync=sync)


@router.get("/fine-tuning/jobs", dependencies=[
    Depends(auth),
    Depends(permissions("read:openai-job"))
])
async def list_user_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    sync: bool = Query(False, description="Sync with OpenAI API for latest statuses"),
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    List all fine-tuning jobs for the current user.
    Set sync=true to fetch fresh status from OpenAI for all jobs (slower).
    """
    logger.info(f"User {get_current_user_id()} listing their fine-tuning jobs (sync={sync})")
    return await service.get_jobs(
        status=status,
        sync=sync
    )


@router.get("/files", dependencies=[
    Depends(auth),
    Depends(permissions("read:openai"))
])
async def list_user_files(
    sync: bool = Query(False, description="Sync with OpenAI API for latest file statuses"),
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    List all uploaded files for the current user.
    Set sync=true to fetch fresh status from OpenAI for all files (slower).
    """
    logger.info(f"User {get_current_user_id()} listing their uploaded files (sync={sync})")
    return await service.get_files(sync=sync)

@router.post("/fine-tuning/jobs/{job_id}/cancel", dependencies=[
    Depends(auth),
    Depends(permissions("write:openai-job"))
])
async def cancel_fine_tuning_job(
    job_id: str,
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    Cancel a running fine-tuning job.
    Only works for jobs with status: validating_files, queued, or running.
    """
    logger.info(f"User {get_current_user_id()} cancelling fine-tuning job: {job_id}")
    return await service.cancel_fine_tuning_job(job_id)


@router.delete("/files/{file_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:openai-file"))
])
async def delete_file(
    file_id: str,
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    Delete an uploaded file from OpenAI.
    Cannot delete files that are being used in active fine-tuning jobs.
    """
    logger.info(f"User {get_current_user_id()} deleting file: {file_id}")
    return await service.delete_file(file_id)

@router.get("/models/fine-tunable", dependencies=[
    Depends(auth),
    Depends(permissions("read:openai-fine-tunable-models"))
])
async def get_fine_tunable_models(
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    Get list of model names that support fine-tuning.
    """
    logger.info(f"User {get_current_user_id()} fetching fine-tunable models")
    return service.get_fine_tunable_models()

@router.delete("/models/{model_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:openai-fine-tuned-model"))
])
async def delete_fine_tuned_model(
    model_id: str,
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    Delete a fine-tuned model from OpenAI.
    Only works for fine-tuned models (format: ft:gpt-4o-mini:org:suffix:abc123).
    Cannot delete base models.
    """
    logger.info(f"User {get_current_user_id()} deleting fine-tuned model: {model_id}")
    return await service.delete_fine_tuned_model(model_id)