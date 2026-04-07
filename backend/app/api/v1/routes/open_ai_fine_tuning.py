import logging
from typing import Optional
from uuid import UUID
from app.core.permissions.constants import Permissions as P
from fastapi import APIRouter, Depends, File, Form, UploadFile, Query
from fastapi.responses import Response
from fastapi_injector import Injected
from app.auth.dependencies import auth, permissions
from app.auth.utils import get_current_user_id
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus
from app.schemas.open_ai_fine_tuning import (
    CreateFineTuningJobRequest,
    FineTuningJobResponse,
    GenerateTrainingFileRequest,
)
from app.schemas.user import UserUpdate
from app.services.open_ai_fine_tuning import OpenAIFineTuningService


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", dependencies=[
    Depends(auth),
    Depends(permissions(P.OpenAI.WRITE_FILE))
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
    Depends(permissions(P.OpenAI.WRITE_JOB))
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
    Depends(permissions(P.OpenAI.READ_JOB))
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
    Depends(permissions(P.OpenAI.READ_JOB))
])
async def get_jobs(
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
    Depends(permissions(P.OpenAI.READ_FILE))
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
    Depends(permissions(P.OpenAI.WRITE_JOB))
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


@router.get("/files/{file_id}/content", dependencies=[
    Depends(auth),
    Depends(permissions(P.OpenAI.READ_FILE))
])
async def download_file(
    file_id: str,
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService)
):
    """
    Download the raw content of an OpenAI file (e.g. training/validation JSONL).
    """
    logger.info(f"User {get_current_user_id()} downloading file: {file_id}")
    content = await service.client.files.content(file_id)
    return Response(
        content=content.read(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_id}.jsonl"'},
    )


@router.delete("/files/{file_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.OpenAI.DELETE_FILE))
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
    Depends(permissions(P.OpenAI.DELETE_FINE_TUNED_MODEL))
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


@router.post("/fine-tuning/generate-from-conversations", dependencies=[
    Depends(auth),
    Depends(permissions(P.OpenAI.WRITE_FILE))
])
async def generate_training_file_from_conversations(
    request: GenerateTrainingFileRequest,
    service: OpenAIFineTuningService = Injected(OpenAIFineTuningService),
):
    """
    Generate a JSONL fine-tuning training file from past conversation logs.

    Extracts the system prompt and tool schemas from the specified agent's workflow,
    then builds one training example per agent response found in each conversation.

    When upload_to_openai=false (default), returns the JSONL as a file download.
    When upload_to_openai=true, uploads to OpenAI and returns the file record.
    """
    logger.info(
        f"User {get_current_user_id()} generating training file "
        f"from {len(request.conversation_ids)} conversations"
    )

    jsonl_bytes = await service.generate_training_file_from_conversations(request)

    if not request.upload_to_openai:
        return Response(
            content=jsonl_bytes,
            media_type="application/jsonl",
            headers={"Content-Disposition": 'attachment; filename="training_data.jsonl"'},
        )

    filename = "training_conversations.jsonl"
    response = await service.client.files.create(
        file=(filename, jsonl_bytes),
        purpose="fine-tune",
    )
    db_record = await service.repository.create_file_record(
        openai_file_id=response.id,
        filename=response.filename,
        purpose=response.purpose,
        bytes=response.bytes,
    )
    return db_record.to_dict()