"""
Workflow Builder API endpoint.

Creates workflows from a structured specification (enhanced format supporting
branching, tool connections, and config overrides).
"""

import json
import logging
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.modules.workflow.builder.build import build_workflow_from_spec
from app.schemas.agent import AgentCreate
from app.services.agent_config import AgentConfigService
from app.services.workflow import WorkflowService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/config/from-builder",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.CREATE))],
)
async def create_workflow_from_builder(
    request: Request,
    workflow_name: str = Body(...),
    workflow_json: str = Body(...),
    workflow_description: str = Body(""),
    agent_service: AgentConfigService = Injected(AgentConfigService),
    workflow_service: WorkflowService = Injected(WorkflowService),
):
    """
    Create a new Agent + Workflow from a structured builder specification.

    The builder format extends the wizard format with:
    - Explicit edges (supporting branching, tool connections)
    - Config overrides per node
    - Non-default sourceHandle/targetHandle for special ports

    Falls back to linear chain if edges are not provided.
    """
    current_user = None
    try:
        current_user = request.state.user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")

    user_id = current_user.id if current_user else None

    # Parse the workflow specification
    try:
        spec = json.loads(workflow_json)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow JSON: {e}",
        )

    # Create agent record
    agent_create = AgentCreate(
        name=workflow_name,
        description=workflow_description or f"Agent created from builder: {workflow_name}",
        is_active=True,
        welcome_message=f"Hello! \nI am {workflow_name},\nHow can I assist you today?",
        welcome_title="Tell me your Today's creative idea!",
        possible_queries=[],
    )
    agent_result = await agent_service.create(agent_create, user_id=user_id)
    agent_id = agent_result.id
    workflow_id = agent_result.workflow_id

    # Load the auto-created workflow record
    workflow_record = await workflow_service.get_by_id(workflow_id)

    # Build workflow from specification
    try:
        result = build_workflow_from_spec(
            spec=spec,
            workflow_name=workflow_name,
            workflow_description=workflow_description,
            user_id=str(user_id) if user_id else "",
            agent_id=str(agent_id),
            workflow_id=str(workflow_id),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Update the workflow record with generated nodes/edges
    workflow_record.nodes = result["nodes"]
    workflow_record.edges = result["edges"]
    workflow_record.executionState = result["executionState"]
    workflow_record.testInput = {}

    await workflow_service.update(workflow_id=workflow_id, data=workflow_record)

    # Build redirect URL using the public base_url (avoids private ._url attribute)
    url = str(request.base_url).rstrip("/") + f"/ai-agents/workflow/{agent_id}"

    return {
        "id": str(workflow_id),
        "name": workflow_name,
        "description": workflow_description,
        "user_id": str(user_id) if user_id else None,
        "agent_id": str(agent_id),
        "url": url,
        "workflow_json": workflow_json,
        "db_record": workflow_record.model_dump(),
    }
