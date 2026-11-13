"""
Workflow Builder API.

Two things live here:

* Drafts. The builder agent edits a server-side draft of a workflow through its
  tools. The canvas uploads its current state as the draft before each message
  and reads the result back afterwards, so nothing has to be parsed out of chat
  text.
* Creation. A new Agent + Workflow is created either from a finished draft or
  from a simplified specification. Both paths are validated before anything is
  saved.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi_injector import Injected
from pydantic import BaseModel, Field

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.modules.workflow.builder import assist
from app.modules.workflow.builder.build import (
    EMPTY_EXECUTION_STATE,
    SpecValidationError,
    build_workflow_from_spec,
)
from app.modules.workflow.builder.draft import (
    STATUS_READY,
    DraftError,
    WorkflowDraft,
    load_draft,
    save_draft,
)
from app.modules.workflow.builder.tools import TOOL_DEFINITIONS
from app.modules.workflow.builder.validation import blocking, validate_workflow
from app.schemas.agent import AgentCreate
from app.services.agent_config import AgentConfigService
from app.services.llm_providers import LlmProviderService
from app.services.llm_usage_read import LlmUsageReadService
from app.services.workflow import WorkflowService

router = APIRouter()
logger = logging.getLogger(__name__)


class AssistRequest(BaseModel):
    snapshot: "CanvasSnapshot"
    action: str
    node_ids: List[str] = Field(default_factory=list)
    instruction: str = ""
    # For add_step: the output of the first node the new step follows.
    source_handle: Optional[str] = None


class ApplyRequest(BaseModel):
    snapshot: "CanvasSnapshot"
    operations: List[Dict[str, Any]]


class CanvasSnapshot(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    selected_node_id: Optional[str] = None
    # Whether the builder's test runs bypass steps that send or create things.
    simulate_actions: bool = True
    # The person's latest test run on the canvas: {"inputs": {...}, "response": {...}, "error": ...}
    last_test_run: Optional[Dict[str, Any]] = None


AssistRequest.model_rebuild()
ApplyRequest.model_rebuild()


async def _tenant_defaults(llm_provider_service: LlmProviderService) -> Dict[str, Any]:
    """Defaults the builder fills into new nodes; missing ones are simply left for the user."""
    try:
        provider = await llm_provider_service.get_default()
        return {"providerId": str(provider.id)}
    except Exception as exc:
        logger.info("No default LLM provider for workflow builder defaults: %s", exc)
        return {}


def _current_user_id(request: Request) -> Optional[UUID]:
    user = getattr(request.state, "user", None)
    return user.id if user else None


def _invalid(issues: List[Dict[str, Any]], message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"message": message, "issues": issues},
    )


# ── Drafts ────────────────────────────────────────────────────────────────


@router.put(
    "/drafts/{conversation_id}",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def put_draft(
    conversation_id: UUID,
    snapshot: CanvasSnapshot,
    llm_provider_service: LlmProviderService = Injected(LlmProviderService),
):
    """
    Start a builder turn from the canvas as the user currently has it
    (including unsaved changes). Replaces the conversation's draft.
    """
    previous = await load_draft(str(conversation_id))
    draft = WorkflowDraft.from_canvas(
        snapshot.nodes,
        snapshot.edges,
        defaults=await _tenant_defaults(llm_provider_service),
        selected_node_id=snapshot.selected_node_id,
        previous=previous,
        last_test_run=snapshot.last_test_run,
    )
    draft.simulate_actions = snapshot.simulate_actions
    await save_draft(str(conversation_id), draft)
    return {"revision": draft.revision, "node_count": len(draft.aliases)}


@router.get(
    "/usage",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_builder_usage(
    conversation_id: Optional[UUID] = None,
    usage_service: LlmUsageReadService = Injected(LlmUsageReadService),
):
    """
    Tokens and cost the Workflow Builder spent: in this conversation and over all of
    them, its test runs included. "The builder" is any agent whose workflow carries a
    Workflow Builder Tools node, so renaming the agent changes nothing here.
    """
    return await usage_service.builder_usage(conversation_id)


@router.get(
    "/tools",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_builder_tools() -> List[Dict[str, str]]:
    """The tools a Workflow Builder Tools node can give an agent; the canvas uses it to describe the node."""
    return [{"name": tool["name"], "description": tool["description"]} for tool in TOOL_DEFINITIONS]


@router.get(
    "/drafts/{conversation_id}",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_draft(conversation_id: UUID):
    """The conversation's draft: canvas-ready nodes and edges, what changed this turn, and open issues."""
    draft = await load_draft(str(conversation_id))
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No workflow draft for this conversation")
    return draft.client_payload()


@router.get(
    "/drafts/{conversation_id}/status",
    dependencies=[Depends(auth)],
)
async def get_draft_status(conversation_id: UUID):
    """
    Whether the builder agent has finalized a workflow in this conversation.

    Readable with the chat API key, so the pre-login onboarding chat can tell
    when the workflow is ready without parsing the agent's replies. ``spec`` is
    the draft in the simplified specification format, for previewing.
    """
    draft = await load_draft(str(conversation_id))
    if draft is None:
        return {"status": "empty", "ready": False, "node_count": 0, "summary": "", "spec": None, "question": None}
    if not draft.nodes:
        return {"status": "empty", "ready": False, "node_count": 0, "summary": "", "spec": None, "question": draft.question}
    return {
        "status": draft.status,
        "ready": draft.status == STATUS_READY and not blocking(draft.issues()),
        "node_count": len(draft.aliases),
        "summary": draft.summary,
        "spec": draft.to_spec(),
        # A question the builder asked (ask_user), so the pre-login chat can show its options too.
        "question": draft.question,
    }


@router.post(
    "/validate",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def validate(snapshot: CanvasSnapshot):
    """Validate a workflow graph without saving anything."""
    issues = validate_workflow(snapshot.nodes, snapshot.edges)
    return {
        "valid": not blocking(issues),
        "issues": [issue.to_dict() for issue in issues],
    }


# ── Focused AI actions on the canvas ──────────────────────────────────────


def _draft_from_snapshot(snapshot: CanvasSnapshot) -> WorkflowDraft:
    return WorkflowDraft.from_canvas(
        snapshot.nodes, snapshot.edges,
        selected_node_id=snapshot.selected_node_id, last_test_run=snapshot.last_test_run,
    )


@router.post(
    "/assist",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def assist_action(body: AssistRequest):
    """
    One focused action on the canvas as it is: explain a step or a group, describe
    the workflow, explain a step in the last test run, suggest test messages,
    review, or propose a change (improved prompt, generated code, optimisations, one
    new step after a given output).
    Proposals are returned, not applied; the canvas applies them with /assist/apply.
    """
    draft = _draft_from_snapshot(body.snapshot)
    try:
        return await assist.run_action(draft, body.action, body.node_ids, body.instruction, body.source_handle)
    except (ValueError, DraftError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/assist/apply",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def assist_apply(body: ApplyRequest):
    """Apply approved operations to the canvas as sent, without a model call; returns the result."""
    from app.modules.workflow.builder.tools import apply_plan

    draft = _draft_from_snapshot(body.snapshot)
    try:
        report = apply_plan(draft, body.operations)
    except DraftError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {**draft.client_payload(), "report": report}


# ── Creation ──────────────────────────────────────────────────────────────


async def create_agent_with_workflow(
    *,
    request: Request,
    workflow_name: str,
    workflow_description: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    agent_service: AgentConfigService,
    workflow_service: WorkflowService,
) -> Dict[str, Any]:
    """
    Create the Agent and fill its workflow with an already validated graph.

    The graph is built and validated by the caller first, so the only thing that
    can still fail here is persistence; in that case the agent is removed again
    rather than left behind with an empty workflow.
    """
    user_id = _current_user_id(request)
    agent_result = await agent_service.create(
        AgentCreate(
            name=workflow_name,
            description=workflow_description or f"Agent created from builder: {workflow_name}",
            is_active=True,
            welcome_message=f"Hello! \nI am {workflow_name},\nHow can I assist you today?",
            welcome_title="Tell me your Today's creative idea!",
            possible_queries=[],
        ),
        user_id=user_id,
    )
    agent_id = agent_result.id
    workflow_id = agent_result.workflow_id

    try:
        workflow_record = await workflow_service.get_by_id(workflow_id)
        workflow_record.nodes = nodes
        workflow_record.edges = edges
        workflow_record.executionState = dict(EMPTY_EXECUTION_STATE)
        workflow_record.testInput = {}
        await workflow_service.update(workflow_id=workflow_id, data=workflow_record)
    except Exception:
        logger.error("Saving the built workflow failed; removing agent %s", agent_id, exc_info=True)
        try:
            await agent_service.delete(agent_id)
        except Exception:
            logger.error("Could not remove agent %s after a failed build", agent_id, exc_info=True)
        raise

    return {
        "id": str(workflow_id),
        "name": workflow_name,
        "description": workflow_description,
        "user_id": str(user_id) if user_id else None,
        "agent_id": str(agent_id),
        "url": str(request.base_url).rstrip("/") + f"/ai-agents/workflow/{agent_id}",
        "db_record": workflow_record.model_dump(),
    }


@router.post(
    "/config/from-builder",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.CREATE))],
)
async def create_workflow_from_builder(
    request: Request,
    workflow_name: str = Body(...),
    workflow_json: Optional[str] = Body(None),
    workflow_description: str = Body(""),
    conversation_id: Optional[UUID] = Body(None),
    dry_run: bool = Body(False),
    agent_service: AgentConfigService = Injected(AgentConfigService),
    workflow_service: WorkflowService = Injected(WorkflowService),
    llm_provider_service: LlmProviderService = Injected(LlmProviderService),
):
    """
    Create a new Agent + Workflow.

    Pass ``conversation_id`` to create it from the draft the builder agent
    finalized in that conversation, or ``workflow_json`` to build it from a
    simplified specification (explicit edges, or a linear chain without them).

    The workflow is validated first. An invalid one returns 400 with
    ``detail.issues`` (node, field, message) and creates nothing. With
    ``dry_run`` nothing is created either way.
    """
    defaults = await _tenant_defaults(llm_provider_service)

    if conversation_id is not None:
        draft = await load_draft(str(conversation_id))
        if draft is None or not draft.nodes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No workflow draft for this conversation",
            )
        errors = blocking(draft.issues())
        if errors:
            raise _invalid(
                [{"node": draft.alias(i.node_id) if i.node_id else None, "field": i.field, "message": i.message}
                 for i in errors],
                "The workflow draft is not valid yet",
            )
        if draft.status != STATUS_READY:
            raise _invalid([], "The workflow draft has not been finalized yet")
        draft.apply_defaults(defaults)
        canvas = draft.to_canvas()
        nodes, edges = canvas["nodes"], canvas["edges"]
    elif workflow_json:
        try:
            spec = json.loads(workflow_json)
        except json.JSONDecodeError as e:
            raise _invalid([], f"Invalid workflow JSON: {e}")
        try:
            built = build_workflow_from_spec(spec, workflow_name, workflow_description, defaults=defaults)
        except SpecValidationError as e:
            raise _invalid(e.issues, "The workflow specification is not valid")
        nodes, edges = built["nodes"], built["edges"]
    else:
        raise _invalid([], "Provide either conversation_id or workflow_json")

    if dry_run:
        return {"valid": True, "nodes": nodes, "edges": edges}

    result = await create_agent_with_workflow(
        request=request,
        workflow_name=workflow_name,
        workflow_description=workflow_description,
        nodes=nodes,
        edges=edges,
        agent_service=agent_service,
        workflow_service=workflow_service,
    )
    result["workflow_json"] = workflow_json
    return result
