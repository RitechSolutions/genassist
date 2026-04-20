from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.prompt_editor import (
    GoldSuiteLinkRequest,
    PromptConfigRead,
    PromptEvalRequest,
    PromptEvalResponse,
    PromptOptimizeRequest,
    PromptOptimizeResponse,
    PromptVersionCreate,
    PromptVersionRead,
)
from app.services.prompt_editor import PromptEditorService

router = APIRouter()


# ---- Versions ----------------------------------------------------------------


@router.get(
    "/versions/{workflow_id}/{node_id}/{prompt_field}",
    response_model=List[PromptVersionRead],
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_versions(
    workflow_id: UUID,
    node_id: str,
    prompt_field: str,
    service: PromptEditorService = Injected(PromptEditorService),
):
    return await service.list_versions(workflow_id, node_id, prompt_field)


@router.post(
    "/versions/{workflow_id}/{node_id}/{prompt_field}",
    response_model=PromptVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def create_version(
    workflow_id: UUID,
    node_id: str,
    prompt_field: str,
    data: PromptVersionCreate,
    service: PromptEditorService = Injected(PromptEditorService),
):
    return await service.create_version(workflow_id, node_id, prompt_field, data)


@router.post(
    "/versions/{version_id}/restore",
    response_model=PromptVersionRead,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def restore_version(
    version_id: UUID,
    service: PromptEditorService = Injected(PromptEditorService),
):
    return await service.restore_version(version_id)


@router.delete(
    "/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def delete_version(
    version_id: UUID,
    service: PromptEditorService = Injected(PromptEditorService),
):
    await service.delete_version(version_id)


@router.delete(
    "/versions/{version_id}/hard",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def hard_delete_version(
    version_id: UUID,
    service: PromptEditorService = Injected(PromptEditorService),
):
    await service.hard_delete_version(version_id)


# ---- Config / Gold Suite -----------------------------------------------------


@router.get(
    "/config/{workflow_id}/{node_id}/{prompt_field}",
    response_model=PromptConfigRead,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def get_config(
    workflow_id: UUID,
    node_id: str,
    prompt_field: str,
    service: PromptEditorService = Injected(PromptEditorService),
):
    return await service.get_or_create_config(workflow_id, node_id, prompt_field)


@router.put(
    "/config/{workflow_id}/{node_id}/{prompt_field}/gold-suite",
    response_model=PromptConfigRead,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def link_gold_suite(
    workflow_id: UUID,
    node_id: str,
    prompt_field: str,
    data: GoldSuiteLinkRequest,
    service: PromptEditorService = Injected(PromptEditorService),
):
    return await service.link_gold_suite(
        workflow_id, node_id, prompt_field,
        suite_id=data.suite_id,
        name=data.name,
    )


# ---- Evaluate & Optimize ----------------------------------------------------


@router.post(
    "/evaluate/{workflow_id}/{node_id}/{prompt_field}",
    response_model=PromptEvalResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.RUN))],
)
async def evaluate_prompt(
    workflow_id: UUID,
    node_id: str,
    prompt_field: str,
    data: PromptEvalRequest,
    service: PromptEditorService = Injected(PromptEditorService),
):
    return await service.evaluate_prompt(
        workflow_id,
        node_id,
        prompt_field,
        prompt_content=data.prompt_content,
        techniques=data.techniques,
        provider_id=data.provider_id,
    )


@router.post(
    "/optimize/{workflow_id}/{node_id}/{prompt_field}",
    response_model=PromptOptimizeResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def optimize_prompt(
    workflow_id: UUID,
    node_id: str,
    prompt_field: str,
    data: PromptOptimizeRequest,
    service: PromptEditorService = Injected(PromptEditorService),
):
    return await service.optimize_prompt(
        workflow_id,
        node_id,
        prompt_field,
        current_prompt=data.current_prompt,
        provider_id=data.provider_id,
        instructions=data.instructions,
        failed_cases=data.failed_cases,
    )
