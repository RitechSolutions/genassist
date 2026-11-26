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

    Kept for existing callers. It first runs the same validated build as
    ``/workflow-builder/config/from-builder`` (a spec without edges becomes a
    linear chain). Wizard JSON that build rejects is created the way this endpoint
    always did, so input it used to accept is never turned away. The response keeps
    its original ``worflow_json`` key (sic) next to ``workflow_json``.
    """
    try:
        result = await create_workflow_from_builder(
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
    except HTTPException as exc:
        wizard_spec = _parse_wizard_json(workflow_json)
        if exc.status_code != status.HTTP_400_BAD_REQUEST or wizard_spec is None:
            raise
        logger.info(
            "Wizard JSON for %r failed the validated build (%s); creating it the legacy way",
            workflow_name,
            exc.detail,
        )
        result = await _create_from_wizard_legacy(
            request=request,
            workflow_name=workflow_name,
            wizard_spec=wizard_spec,
            agent_service=agent_service,
            workflow_service=workflow_service,
        )
    result["workflow_json"] = workflow_json
    result["worflow_json"] = workflow_json  # the original, misspelt key existing callers read
    return result


def _parse_wizard_json(workflow_json: str) -> Optional[Dict[str, Any]]:
    """
    The wizard JSON parsed, or None when it is not JSON or not wizard-shaped (an
    object with a ``workflow`` list): those keep their 400 instead of crashing the
    legacy generator.
    """
    try:
        spec = json.loads(workflow_json)
    except (TypeError, ValueError):
        return None
    if not isinstance(spec, dict) or not isinstance(spec.get("workflow"), list):
        return None
    return spec


async def _create_from_wizard_legacy(
    *,
    request: Request,
    workflow_name: str,
    wizard_spec: Dict[str, Any],
    agent_service: AgentConfigService,
    workflow_service: WorkflowService,
) -> Dict[str, Any]:
    """
    This endpoint's behaviour before the validated build: nodes generated from the
    wizard JSON as given, no edges, no validation. Only reached for wizard JSON the
    validated build rejects.
    """
    current_user = getattr(request.state, "user", None)
    agent_result = await agent_service.create(
        AgentCreate(
            name=workflow_name,
            description=f"Agent created from wizard: {workflow_name}",
            is_active=True,
            welcome_message=f"Hello! \nI am {workflow_name},\nHow can I assist you today?",
            welcome_title="Tell me your Today's creative idea!",
            possible_queries=[],
        ),
        user_id=current_user.id if current_user else None,
    )
    agent_id = agent_result.id
    workflow_id = agent_result.workflow_id

    try:
        workflow_record = await workflow_service.get_by_id(workflow_id)
        wizard = WorkflowManager(
            name=workflow_record.name,
            description=workflow_record.description,
            user_id=workflow_record.user_id,
            agent_id=workflow_record.agent_id,
            workflow_id=workflow_record.id,
        )
        workflow_record.nodes = wizard.generate_nodes_from_wizard(input_data=wizard_spec)
        workflow_record.edges = []
        # Required so Studio does not crash on the new workflow.
        workflow_record.executionState = wizard.generate_execution_state_from_wizard(input_data=wizard_spec)
        workflow_record.testInput = {}
        await workflow_service.update(workflow_id=workflow_id, data=workflow_record)
    except Exception:
        logger.error("Saving the wizard workflow failed; removing agent %s", agent_id, exc_info=True)
        try:
            await agent_service.delete(agent_id)
        except Exception:
            logger.error("Could not remove agent %s after a failed wizard build", agent_id, exc_info=True)
        raise

    return {
        "id": str(workflow_id),
        "name": workflow_name,
        "description": workflow_record.description,
        "user_id": str(workflow_record.user_id) if workflow_record.user_id else None,
        "agent_id": str(agent_id),
        "url": str(request.base_url).rstrip("/") + f"/ai-agents/workflow/{agent_id}",
        "db_record": workflow_record.model_dump(),
    }


@router.get(
    "/config/available-node-types",
    dependencies=[Depends(auth)]
)
async def get_available_node_types():
    return list(NODE_DIALOG_SCHEMAS.keys())
