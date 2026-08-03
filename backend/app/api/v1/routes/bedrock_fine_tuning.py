import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.auth.utils import get_current_user_id
from app.core.permissions.constants import Permissions as P
from app.core.utils.cache_headers import no_store_headers
from app.core.utils.enums.bedrock_fine_tuning_enum import BedrockJobStatus
from app.schemas.bedrock_fine_tuning import (
    CreateBedrockFineTuningJobRequest,
    GenerateBedrockTrainingFileRequest,
)
from app.services.bedrock_fine_tuning import BedrockFineTuningService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.WRITE_TRAINING_DATA)),
])
async def upload_training_data(
    file: UploadFile = File(...),
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Upload a JSONL training file to S3 and return its s3:// URI."""
    logger.info(f"User {get_current_user_id()} uploading Bedrock training data {file.filename}")
    content = await file.read()
    s3_uri = await service.upload_training_data(content, file.filename)
    return {"s3_uri": s3_uri, "filename": file.filename, "bytes": len(content)}


@router.get("/training-files", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.READ_JOB)),
])
async def list_training_files(
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """List JSONL training files already uploaded/generated in S3."""
    return await service.list_training_files()


@router.post("/fine-tuning/jobs", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.WRITE_JOB)),
])
async def create_fine_tuning_job(
    job_request: CreateBedrockFineTuningJobRequest,
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Create a Bedrock (Nova) fine-tuning job."""
    logger.info(f"User {get_current_user_id()} creating Bedrock fine-tuning job")
    job = await service.create_fine_tuning_job(job_request=job_request)
    return job.to_dict()


@router.get("/fine-tuning/jobs/{job_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.READ_JOB)),
])
async def get_fine_tuning_job(
    job_id: UUID,
    sync: bool = Query(True, description="Sync with Bedrock for latest status"),
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Retrieve a Bedrock fine-tuning job. Set sync=false to use cached data."""
    logger.info(f"Retrieving Bedrock fine-tuning job: {job_id} (sync={sync})")
    return await service.get_fine_tuning_job(job_id, sync=sync)


@router.get("/fine-tuning/jobs", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.READ_JOB)),
])
async def get_jobs(
    status: Optional[BedrockJobStatus] = Query(None, description="Filter by job status"),
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """List all Bedrock fine-tuning jobs (cached).

    Use POST /fine-tuning/jobs/sync to refresh active jobs from Bedrock.
    """
    logger.info(f"User {get_current_user_id()} listing Bedrock fine-tuning jobs")
    return await service.get_jobs(status=status)


@router.post("/fine-tuning/jobs/sync", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.READ_JOB)),
])
async def sync_jobs(
    status: Optional[BedrockJobStatus] = Query(None, description="Filter by job status"),
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Refresh active jobs from Bedrock, then return the list.

    This is the only endpoint that triggers a sync.
    """
    logger.info(f"User {get_current_user_id()} syncing Bedrock fine-tuning jobs")
    return await service.get_jobs(status=status, sync=True)


@router.post("/fine-tuning/jobs/{job_id}/cancel", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.WRITE_JOB)),
])
async def cancel_fine_tuning_job(
    job_id: UUID,
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Stop a running Bedrock fine-tuning job."""
    logger.info(f"User {get_current_user_id()} stopping Bedrock fine-tuning job: {job_id}")
    job = await service.cancel_fine_tuning_job(job_id)
    return job.to_dict()


@router.delete("/fine-tuning/jobs/{job_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.WRITE_JOB)),
])
async def delete_fine_tuning_job(
    job_id: UUID,
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Remove a Bedrock fine-tuning job from the list (soft delete).

    Does not stop a running AWS job (use cancel) or delete a deployment.
    """
    logger.info(f"User {get_current_user_id()} deleting Bedrock fine-tuning job: {job_id}")
    await service.delete_job(job_id)
    return {"id": str(job_id), "deleted": True}


@router.post("/fine-tuning/jobs/{job_id}/deploy", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.DEPLOY_MODEL)),
])
async def deploy_custom_model(
    job_id: UUID,
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Create an on-demand custom model deployment for a completed Nova job."""
    logger.info(f"User {get_current_user_id()} deploying Bedrock custom model for job: {job_id}")
    job = await service.deploy_custom_model(job_id)
    return job.to_dict()


@router.post("/fine-tuning/jobs/{job_id}/undeploy", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.UNDEPLOY_MODEL)),
])
async def undeploy_custom_model(
    job_id: UUID,
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Tear down the on-demand custom model deployment for a Nova job."""
    logger.info(f"User {get_current_user_id()} undeploying Bedrock custom model for job: {job_id}")
    job = await service.undeploy_custom_model(job_id)
    return job.to_dict()


@router.get("/models/fine-tunable", dependencies=[
    Depends(auth),
])
async def get_fine_tunable_models(
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Get the list of Nova base models that support fine-tuning."""
    logger.info(f"User {get_current_user_id()} fetching Bedrock fine-tunable models")
    return await service.get_fine_tunable_models()


@router.post("/fine-tuning/generate-from-conversations", dependencies=[
    Depends(auth),
    Depends(permissions(P.Bedrock.WRITE_TRAINING_DATA)),
])
async def generate_training_file_from_conversations(
    request: GenerateBedrockTrainingFileRequest,
    service: BedrockFineTuningService = Injected(BedrockFineTuningService),
):
    """Generate a Nova JSONL training file from past conversation logs.

    When upload_to_s3=false (default), returns the JSONL as a file download.
    When upload_to_s3=true, uploads to S3 and returns the s3:// URI.
    """
    logger.info(
        f"User {get_current_user_id()} generating Bedrock training file "
        f"from {len(request.conversation_ids)} conversations"
    )
    jsonl_bytes = await service.generate_training_file_from_conversations(request)

    if not request.upload_to_s3:
        return Response(
            content=jsonl_bytes,
            media_type="application/jsonl",
            headers={
                "Content-Disposition": 'attachment; filename="nova_training_data.jsonl"',
                **no_store_headers(),
            },
        )

    s3_uri = await service.upload_training_data(jsonl_bytes, "nova_training_conversations.jsonl")
    return {"s3_uri": s3_uri, "bytes": len(jsonl_bytes)}
