import time
import logging
import uuid
from typing import List, Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi_injector import Injected
from app.modules.workflow.utils import generate_python_function_template

from app.schemas.workflow import Workflow, WorkflowCreate, WorkflowUpdate
from app.auth.dependencies import auth, permissions

from app.services.workflow import WorkflowService
from app.dependencies.injector import injector
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.engine.workflow_engine import WorkflowEngine

from app.schemas.dynamic_form_schemas.nodes import get_node_dialog_schema as get_schema


router = APIRouter()
logger = logging.getLogger(__name__)

# Supported node types
SUPPORTED_NODE_TYPES = [
    "chatInputNode",
    "chatOutputNode",
    "routerNode",
    "agentNode",
    "apiToolNode",
    "templateNode",
    "llmModelNode",
    "knowledgeBaseNode",
    "pythonToolNode",
    "dataMapperNode",
    "toolBuilderNode",
    "slackMessageNode",
    "calendarEventNode",
    "readMailsNode",
    "gmailNode",
    "whatsappToolNode",
    "zendeskTicketNode",
    "pythonCodeNode",
    "sqlNode",
    "aggregatorNode",
    "jiraNode",
    "mlModelInferenceNode",
    "trainDataSourceNode",
    "threadRAGNode",
    "preprocessingNode",
    "trainModelNode",
]


@router.post(
    "/",
    response_model=Workflow,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions("create:workflow"))],
)
async def create_workflow(
    workflow_data: WorkflowCreate,
    request: Request,
    service: WorkflowService = Injected(WorkflowService),
):
    """
    Create a new workflow
    """
    current_user = request.state.user
    workflow = WorkflowCreate(
        name=workflow_data.name,
        description=workflow_data.description,
        nodes=workflow_data.nodes,
        edges=workflow_data.edges,
        executionState=workflow_data.executionState,
        version=workflow_data.version,
        user_id=current_user.id,
        agent_id=workflow_data.agent_id,
    )
    workflow = await service.create(workflow)
    return workflow


@router.get(
    "/{workflow_id}",
    response_model=Workflow,
    dependencies=[Depends(auth), Depends(permissions("read:workflow"))],
)
async def get_workflow(
    workflow_id: UUID, service: WorkflowService = Injected(WorkflowService)
):
    """
    Get a workflow by ID
    """
    workflow = await service.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get(
    "/",
    response_model=List[Workflow],
    dependencies=[Depends(auth), Depends(permissions("read:workflow"))],
)
async def get_workflows(service: WorkflowService = Injected(WorkflowService)):
    """
    Get all workflows for the current user
    """
    workflows = await service.get_all()
    return workflows


@router.put(
    "/{workflow_id}",
    dependencies=[Depends(auth), Depends(permissions("update:workflow"))],
    response_model=Workflow,
)
async def update_workflow(
    workflow_id: UUID,
    workflow_data: WorkflowUpdate,
    service: WorkflowService = Injected(WorkflowService),
):
    """
    Update a workflow
    """
    logger.info(f"Updating workflow: {workflow_id}")
    logger.info(f"Workflow data: {workflow_data}")
    workflow = await service.get_by_id(workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Update the workflow
    workflow.name = workflow_data.name
    workflow.description = workflow_data.description
    workflow.nodes = workflow_data.nodes
    workflow.edges = workflow_data.edges
    if workflow_data.testInput:
        workflow.testInput = workflow_data.testInput
    if workflow_data.executionState:
        workflow.executionState = workflow_data.executionState
    workflow.version = workflow_data.version
    updated_workflow = await service.update(workflow_id, workflow)
    return updated_workflow


@router.delete(
    "/{workflow_id}",
    dependencies=[Depends(auth), Depends(permissions("delete:workflow"))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workflow(
    workflow_id: UUID,
    request: Request,
    service: WorkflowService = Injected(WorkflowService),
):
    """
    Delete a workflow
    """
    current_user = request.state.user
    workflow = await service.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Check if the user owns this workflow
    if workflow.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this workflow"
        )

    await service.delete(workflow_id)


@router.post(
    "/{workflow_id}/execute",
    dependencies=[Depends(auth), Depends(permissions("execute:workflow"))],
)
async def execute_workflow(
    workflow_id: UUID,
    input_data: Dict[str, Any],
):
    """
    Execute a workflow with path-based input data.

    The input_data contains path-based keys that specify where in the workflow context
    the values should be placed. This allows the workflow to be initialized with
    specific values that node processors can access later.

    Examples of path-based keys:
    - "node_outputs.nodeId.output" -> Sets workflow.state.node_outputs[nodeId]["output"] = value
    - "metadata.message" -> Sets workflow.state.metadata["message"] = value
    - "user_id" -> Sets workflow.state.user_id = value (direct context)

    This enables scenarios like:
    - Pre-populating node outputs from previous workflow runs
    - Setting metadata that nodes can access during execution
    - Initializing workflow state with known values
    """

    # Get the input message from the request body
    input_data = input_data.get("input_data", {})
    if not input_data:
        raise HTTPException(status_code=400, detail="Input data is required")

    try:
        # Get the workflow from the service
        workflow_service = injector.get(WorkflowService)
        workflow = await workflow_service.get_by_id(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Use the new engine approach
        workflow_config = {
            "id": str(workflow_id),
            "nodes": workflow.nodes,
            "edges": workflow.edges,
        }
        thread_id = input_data.get("thread_id", str(uuid.uuid4()))
        workflow_engine = WorkflowEngine.get_instance()
        workflow_engine.build_workflow(workflow_config)

        state = await workflow_engine.execute_from_node(
            str(workflow_id), input_data=input_data, thread_id=thread_id
        )

        return state.format_state_as_response()

    except Exception as e:
        logger.error(f"Error executing workflow with new engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test", dependencies=[Depends(auth), Depends(permissions("test:workflow"))]
)
async def test_workflow(
    test_data: Dict[str, Any],
    workflow_id: Optional[UUID] = None,
    workflow_service: WorkflowService = Injected(WorkflowService),
):
    """
    Test a workflow configuration without saving it

    Request body should contain:
    - configuration: The workflow configuration (if workflow_id not provided)
    - message: The input message to test with

    If workflow_id is provided, the workflow will be fetched from the database.
    """
    # Extract the input data from the request body
    input_data = test_data.get("input_data", {})

    # Validate input data
    if not input_data:
        raise HTTPException(status_code=400, detail="Input message is required")

    try:
        # Determine workflow source
        if workflow_id:
            # Get workflow from database using workflow_id
            db_workflow = await workflow_service.get_by_id(workflow_id)
            if not db_workflow:
                raise HTTPException(
                    status_code=404, detail=f"Workflow with id {workflow_id} not found"
                )

            workflow_config = {
                "id": str(workflow_id),
                "nodes": db_workflow.nodes,
                "edges": db_workflow.edges,
            }
        else:
            # Use workflow from request body (current behavior)
            input_workflow = test_data.get("workflow", {})

            if not input_workflow:
                raise HTTPException(
                    status_code=400,
                    detail="Workflow model is required when workflow_id is not provided",
                )

            workflow = WorkflowUpdate(**input_workflow)
            workflow_config = {
                "id": "test-workflow",
                "nodes": workflow.nodes,
                "edges": workflow.edges,
            }

        # Use the new engine approach
        workflow_engine = WorkflowEngine.get_instance()
        workflow_engine.build_workflow(workflow_config)

        thread_id = input_data.get("thread_id", str(uuid.uuid4()))
        state = await workflow_engine.execute_from_node(
            workflow_config["id"], input_data=input_data, thread_id=thread_id
        )

        return state.format_state_as_response()

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error testing workflow with new engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dialog_schema/{node_type}", dependencies=[Depends(auth)])
async def get_node_dialog_schema(node_type: str):
    if node_type not in SUPPORTED_NODE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported node type: {node_type}. Supported types: {SUPPORTED_NODE_TYPES}",
        )

    return get_schema(node_type)


@router.post(
    "/test-node", dependencies=[Depends(auth), Depends(permissions("test:workflow"))]
)
async def test_individual_node(test_data: Dict[str, Any]):
    """
    Test an individual node with the new engine.

    This unified endpoint replaces all the previous individual test endpoints:
    - /test-knowledge-tool → Use node_type: "knowledgeToolNode"
    - /test-python-function → Use node_type: "pythonToolNode"
    - /test-read-mails → Use node_type: "readMailsToolNode"
    - /test-tool-builder → Use node_type: "toolBuilderNode"
    - /calendar-event/test-create-event → Use node_type: "calendarEventsNode"
    """
    # Extract parameters from request body

    node_type = test_data.get("node_type")
    node_config = test_data.get("node_config", {})
    input_data = test_data.get("input_data", {})

    # Validate required inputs
    if not node_type:
        raise HTTPException(status_code=400, detail="node_type is required")

    if not node_config:
        raise HTTPException(status_code=400, detail="node_config is required")

    # Validate node type is supported
    if node_type not in SUPPORTED_NODE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported node type: {node_type}. Supported types: {SUPPORTED_NODE_TYPES}",
        )

    try:
        # Create a unique test ID
        test_id = f"test-{node_type}-{int(time.time())}"

        # Build workflow configuration with single node
        workflow_config = {
            "id": test_id,
            "nodes": [{"id": test_id, "type": node_type, "data": node_config}],
            "edges": [],
        }
        workflow_engine = WorkflowEngine.get_instance()

        # Build and execute the workflow
        workflow_engine.build_workflow(workflow_config)
        state = await workflow_engine.execute_from_node(test_id, input_data=input_data)

        return state.format_state_as_response()

    except Exception as e:
        logger.error(f"Error testing {node_type} node: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-python-template", response_model=Dict[str, Any])
async def generate_python_template(
    test_data: Dict[str, Any],
):
    """
    Generate a Python function template based on a tool's parameter schema.
    Optionally, if a 'prompt' is provided, use the LLM to modify the template with extra logic described by the prompt.
    """
    try:
        parameters_schema = test_data.get("parameters_schema", {})
        prompt = test_data.get("prompt")
        code = test_data.get("code")
        # If code and prompt are both provided and not empty, use code as template
        if code and prompt:
            template = code
        else:
            # Generate code template based on parameters
            template = generate_python_function_template(parameters_schema)

        if prompt:
            # Use LLM to modify the template with the extra logic
            llm_provider = injector.get(LLMProvider)
            # Get the default model (first config or default)
            configs = llm_provider.get_all_configurations()
            if not configs:
                raise HTTPException(
                    status_code=500, detail="No LLM provider configuration found."
                )
            default_model_id = str(
                next(
                    (c for c in configs if getattr(c, "is_default", 0) == 1), configs[0]
                ).id
            )
            llm = await llm_provider.get_model(default_model_id)
            # Compose the LLM prompt
            llm_prompt = f"""
You are an expert Python developer. You are given a Python function template below. 
            Modify the function so that inside the 'executable_function', you add the following logic described by the user, you do not change anything else from the template, including comments:

---
USER INSTRUCTION:
{prompt}
---

PYTHON FUNCTION TEMPLATE:
{template}

Return ONLY the modified Python code, nothing else.
"""
            # Call the LLM (assume sync for now, but wrap in run_in_executor for async)
            import asyncio

            loop = asyncio.get_event_loop()

            def sync_llm_call():
                return llm.invoke([{"role": "user", "content": llm_prompt}]).content

            modified_template = await loop.run_in_executor(None, sync_llm_call)
            # Remove code block markers if present
            if modified_template.strip().startswith("```python"):
                modified_template = modified_template.strip()[
                    len("```python") :
                ].lstrip("\n")
            if modified_template.strip().endswith("```"):
                modified_template = modified_template.strip()
                if modified_template.endswith("```"):
                    modified_template = modified_template[:-3].rstrip("\n")
            template = modified_template

        return {"template": template}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating Python template: {str(e)}"
        )


@router.get(
    "/logging/__debug_logging__",
    dependencies=[Depends(auth), Depends(permissions("test:workflow"))],
)
async def debug_logging_probe():
    root = logging.getLogger()
    return {
        "logger_name": logger.name,
        "effective_level": logging.getLevelName(logger.getEffectiveLevel()),
        "handlers_on_logger": [type(h).__name__ for h in logger.handlers],
        "propagate": logger.propagate,
        "root_level": logging.getLevelName(root.getEffectiveLevel()),
        "root_handlers": [type(h).__name__ for h in root.handlers],
    }
