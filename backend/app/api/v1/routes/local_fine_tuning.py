from typing import List

from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.local_fine_tuning import (
    CreateDeploymentRequest,
    CreateLocalFineTuneJobRequest,
    DeleteJobFilesRequest,
    DeleteJobFilesResponse,
    DeploymentStopResponse,
    LocalFineTuneDeployment,
    LocalFineTuneDeploymentHealth,
    LocalFineTuneJob,
    LocalFineTuneJobEvent,
    LocalFineTuneSupportedModel,
    SystemGpusResponse,
    TestInferenceRequest,
    TestInferenceResponse,
)
from app.services.local_fine_tuning import LocalFineTuningService

router = APIRouter()


@router.get(
    "/supported-models",
    response_model=List[LocalFineTuneSupportedModel],
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.READ))],
)
async def list_supported_models(
    skip: int = 0,
    limit: int = 10,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.list_supported_models(skip=skip, limit=limit)


@router.get(
    "/system/gpus",
    response_model=SystemGpusResponse,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.READ))],
)
async def list_system_gpus(
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.list_system_gpus()


@router.get(
    "/jobs",
    response_model=List[LocalFineTuneJob],
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.READ))],
)
async def list_jobs(
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.list_jobs()


@router.get(
    "/jobs/{job_id}",
    response_model=LocalFineTuneJob,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.READ))],
)
async def get_job(
    job_id: str,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.get_job(job_id)


@router.get(
    "/jobs/{job_id}/events",
    response_model=List[LocalFineTuneJobEvent],
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.READ))],
)
async def list_job_events(
    job_id: str,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.list_job_events(job_id)


@router.post(
    "/jobs",
    response_model=LocalFineTuneJob,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.CREATE))],
)
async def create_job(
    payload: CreateLocalFineTuneJobRequest,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.create_job(payload)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=LocalFineTuneJob,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.CANCEL))],
)
async def cancel_job(
    job_id: str,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.cancel_job(job_id)


@router.delete(
    "/jobs/{job_id}/files",
    response_model=DeleteJobFilesResponse,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.DELETE))],
)
async def delete_job_files(
    job_id: str,
    delete_data_files: bool = True,
    delete_checkpoints: bool = True,
    delete_model: bool = False,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    params = DeleteJobFilesRequest(
        delete_data_files=delete_data_files,
        delete_checkpoints=delete_checkpoints,
        delete_model=delete_model,
    )
    return await service.delete_job_files(job_id, params)


@router.get(
    "/deployments",
    response_model=List[LocalFineTuneDeployment],
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.READ))],
)
async def list_deployments(
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.list_deployments()


@router.get(
    "/deployments/{deployment_id}",
    response_model=LocalFineTuneDeployment,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.READ))],
)
async def get_deployment(
    deployment_id: str,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.get_deployment(deployment_id)


@router.post(
    "/deployments",
    response_model=LocalFineTuneDeployment,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.DEPLOY))],
)
async def create_deployment(
    payload: CreateDeploymentRequest,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.create_deployment(payload)


@router.delete(
    "/deployments/{deployment_id}",
    response_model=DeploymentStopResponse,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.DELETE))],
)
async def stop_deployment(
    deployment_id: str,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.stop_deployment(deployment_id)


@router.get(
    "/deployments/{deployment_id}/health",
    response_model=LocalFineTuneDeploymentHealth,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.READ))],
)
async def deployment_health(
    deployment_id: str,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.deployment_health(deployment_id)


@router.post(
    "/deployments/{deployment_id}/test-inference",
    response_model=TestInferenceResponse,
    dependencies=[Depends(auth), Depends(permissions(P.LocalFineTuning.TEST))],
)
async def test_inference(
    deployment_id: str,
    body: TestInferenceRequest,
    service: LocalFineTuningService = Injected(LocalFineTuningService),
):
    return await service.test_inference(deployment_id, body.message)
