import time
import logging
import uuid
import json
from typing import List, Dict, Any, Optional
from uuid import UUID
from app.modules.workflow.manage.workflow_manager import WorkflowManager
from app.schemas.agent import AgentCreate, AgentRead
from app.services.agent_config import AgentConfigService
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from fastapi_injector import Injected
from app.modules.workflow.utils import generate_python_function_template

from app.schemas.workflow import Workflow, WorkflowCreate, WorkflowUpdate
from app.auth.dependencies import auth, permissions

from app.services.workflow import WorkflowService
from app.services.llm_providers import LlmProviderService
from app.api.v1.routes.workflow_builder import create_workflow_from_builder
from app.dependencies.injector import injector
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.core.permissions.constants import Permissions as P
from app.schemas.dynamic_form_schemas.nodes import NODE_DIALOG_SCHEMAS


router = APIRouter()
logger = logging.getLogger(__name__)



@router.post(
    "/config/from-wizard",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.CREATE))],
)
async def create_workflow_from_wizard(
    request: Request,
    workflow_name: str = Body(...),
    workflow_json: str = Body(...),
    agent_service: AgentConfigService = Injected(AgentConfigService),
    workflow_service: WorkflowService = Injected(WorkflowService),
    llm_provider_service: LlmProviderService = Injected(LlmProviderService),
):
    """
    Create a new Agent and its workflow from the wizard JSON.

    Kept for existing callers. It runs the same validated build as
    ``/workflow-builder/config/from-builder``: a spec without edges becomes a
    linear chain.
    """
    return await create_workflow_from_builder(
        request=request,
        workflow_name=workflow_name,
        workflow_json=workflow_json,
        workflow_description="",
        conversation_id=None,
        dry_run=False,
        agent_service=agent_service,
        workflow_service=workflow_service,
        llm_provider_service=llm_provider_service,
    )


@router.get(
    "/config/available-node-types",
    dependencies=[Depends(auth)]
)
async def get_available_node_types():
    return list(NODE_DIALOG_SCHEMAS.keys())

# @router.get(
#     "",
#     response_model=List[Workflow],
#     dependencies=[Depends(auth), Depends(permissions("read:workflow"))],
# )
# async def get_workflows(service: WorkflowService = Injected(WorkflowService)):
#     """
#     Get all workflows for the current user
#     """
#     workflows = await service.get_all()
#     return workflows

