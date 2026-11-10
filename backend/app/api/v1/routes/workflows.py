import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.keepalive_json_response import keepalive_json
from app.core.permissions.constants import Permissions as P
from app.core.tenant_scope import get_tenant_context
from app.core.utils.string_utils import truncate_for_log
from app.core.utils.uuid_utils import coerce_uuid
from app.dependencies.dependency_injection import RedisString
from app.dependencies.injector import injector
from app.modules.workflow import training_jobs
from app.modules.workflow.test_runs import run_workflow_test
from app.modules.workflow.engine.pii_anonymizer import PIIAnonymizer
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.usage_context import WorkflowUsageContext
from app.modules.workflow.utils import generate_python_function_template
from app.schemas.dynamic_form_schemas.nodes import NODE_DIALOG_SCHEMAS
from app.schemas.workflow import Workflow, WorkflowCreate, WorkflowMinimal, WorkflowSummary, WorkflowUpdate
from app.services.llm_providers import LlmProviderService
from app.services.workflow import WorkflowService

router = APIRouter()
logger = logging.getLogger(__name__)

_pii_redactor = PIIAnonymizer(entities=["CREDIT_CARD", "IBAN_CODE", "US_SSN"])

# Supported node types
SUPPORTED_NODE_TYPES = [
    "chatInputNode",
    "webhookTriggerNode",
    "chatOutputNode",
    "routerNode",
    "switchNode",
    "filterNode",
    "loopNode",
    "agentNode",
    "subAgentNode",
    "apiToolNode",
    "openApiNode",
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
    "salesforceCaseNode",
    "pythonCodeNode",
    "sqlNode",
    "aggregatorNode",
    "jiraNode",
    "mlModelInferenceNode",
    "trainDataSourceNode",
    "threadRAGNode",
    "preprocessingNode",
    "trainModelNode",
    "mcpNode",
    "workflowBuilderToolsNode",
    "workflowExecutorNode",
    "humanInTheLoopNode",
    "setStateNode",
    "guardrailProvenanceNode",
    "guardrailNliNode",
    "fileReaderNode",
    "externalAgentNode",
    "ttsNode",
    "sttNode",
    "voiceAgentNode",
    "createWorkflowScheduleNode",
    "webScraperNode",
    "webSearchNode",
    "htmlToImageNode",
    "nlpNode",
]


@router.post(
    "",
    response_model=Workflow,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.CREATE))],
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
        settings=workflow_data.settings,
        version=workflow_data.version,
        user_id=current_user.id,
        agent_id=workflow_data.agent_id,
    )
    workflow = await service.create(workflow)
    return workflow


@router.get(
    "/node_schemas",
    dependencies=[Depends(auth)]
)
async def get_node_dialog_schemas():
    return NODE_DIALOG_SCHEMAS


@router.get(
    "",
    response_model=List[Workflow],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_workflows(service: WorkflowService = Injected(WorkflowService)):
    """
    Get all workflows for the current user
    """
    workflows = await service.get_all()
    return workflows


@router.get(
    "/minimal",
    response_model=List[WorkflowMinimal],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_workflows_minimal(service: WorkflowService = Injected(WorkflowService)):
    """
    Lightweight list of the workflows the caller can see, matching Agent Studio.
    """
    return await service.get_visible_minimal()


@router.get(
    "/summaries",
    response_model=List[WorkflowSummary],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_workflow_summaries(
    agent_id: UUID, service: WorkflowService = Injected(WorkflowService)
):
    return await service.get_summaries_by_agent(agent_id)


@router.put(
    "/{workflow_id}",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
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
    logger.info("Workflow data: %s", truncate_for_log(str(workflow_data)))
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
    if workflow_data.settings is not None:
        workflow.settings = workflow_data.settings
    workflow.version = workflow_data.version

    updated_workflow = await service.update(workflow_id, workflow)
    return updated_workflow


@router.delete(
    "/{workflow_id}",
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.DELETE))],
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
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.EXECUTE))],
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

    # Redact cardholder data before it enters the workflow engine
    if isinstance(input_data.get("message"), str):
        input_data["message"] = _pii_redactor.redact(input_data["message"])

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
        workflow_engine = WorkflowEngine(workflow_config)

        state = await workflow_engine.execute_from_node(
            input_data=input_data,
            thread_id=thread_id,
            usage_context=WorkflowUsageContext(
                source="workflow_api",
                workflow_id=coerce_uuid(workflow_engine.workflow_id),
                defer_capture=True,
            ),
        )

        return state.format_state_as_response()

    except Exception as e:
        logger.error(f"Error executing workflow with new engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _training_job_owner() -> str:
    """The signed-in user a training test job belongs to.

    Jobs are scoped to their owner (status reads, cancelling, one job at a
    time), so a caller without a user id, e.g. an API key with no user,
    can't start one: such callers would all share one anonymous owner.
    """
    user_id = get_current_user_id()
    if not user_id:
        raise AppException(
            error_key=ErrorKey.ML_TRAINING_JOB_NEEDS_USER,
            status_code=403,
            error_detail="Testing a model training needs a signed-in user. Use a user's login or an API key that belongs to a user.",
        )
    return str(user_id)


def _training_job_store() -> training_jobs.TrainingJobStore:
    return training_jobs.TrainingJobStore(injector.get(RedisString))


async def _queue_training_job(
    kind: str, training_nodes: List[Dict[str, Any]], payload: Dict[str, Any]
) -> JSONResponse:
    """
    Run a test that trains a model on the "ml" worker instead of in this request.

    An oversized hyperparameter search is refused here, before anything is
    queued. Returns 202 with the job; the client polls GET /workflows/test-jobs/{job_id}.
    A user who already has a queued or running job gets 409; GET
    /workflows/test-jobs/active returns that job, to follow or cancel it.
    """
    for node_data in training_nodes:
        training_jobs.check_training_config(node_data)

    tenant_id = get_tenant_context()
    owner = _training_job_owner()
    store = _training_job_store()
    # One job per user at a time: the "ml" queue is shared by every tenant.
    job, running = await store.start(tenant_id, owner, kind)
    if running is not None:
        raise AppException(
            error_key=ErrorKey.ML_TRAINING_JOB_ALREADY_RUNNING,
            status_code=409,
            error_detail="You already have a training test running. Wait for it to finish or cancel it, then run the test again.",
        )
    try:
        from app.tasks.ml_training_job_tasks import run_training_job_task

        run_training_job_task.delay(job["job_id"], tenant_id, jsonable_encoder({**payload, "kind": kind}))
    except Exception as e:
        logger.error(f"Could not queue training job {job['job_id']}: {e}")
        await store.update(
            tenant_id,
            job["job_id"],
            expect=(training_jobs.STATUS_QUEUED,),
            status=training_jobs.STATUS_FAILED,
            error="Could not start the training job.",
        )
        raise HTTPException(status_code=503, detail="Could not start the training job. Try again.")

    logger.info(f"Queued training job {job['job_id']} ({kind})")
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=training_jobs.public_view(job))


def _training_job_not_found() -> AppException:
    return AppException(
        error_key=ErrorKey.ML_TRAINING_JOB_NOT_FOUND,
        status_code=404,
        error_detail="The training job was not found or has expired.",
    )


async def _owned_training_job(store: training_jobs.TrainingJobStore, job_id: str) -> Dict[str, Any]:
    owner = _training_job_owner()
    job = await store.get(get_tenant_context(), job_id)
    if job is None or job.get("user_id") != owner:
        raise _training_job_not_found()
    return job


@router.get(
    "/test-jobs/active", dependencies=[Depends(auth), Depends(permissions(P.Workflow.TEST))]
)
async def get_active_training_job():
    """The user's queued or running training test, to follow or cancel after leaving it."""
    job = await _training_job_store().active_job(get_tenant_context(), _training_job_owner())
    if job is None:
        raise _training_job_not_found()
    return training_jobs.public_view(job)


@router.get(
    "/test-jobs/{job_id}", dependencies=[Depends(auth), Depends(permissions(P.Workflow.TEST))]
)
async def get_training_job(job_id: str):
    """Status, progress and (once finished) result of a training test run."""
    store = _training_job_store()
    return training_jobs.public_view(await _owned_training_job(store, job_id))


@router.post(
    "/test-jobs/{job_id}/cancel", dependencies=[Depends(auth), Depends(permissions(P.Workflow.TEST))]
)
async def cancel_training_job(job_id: str):
    """Cancel a queued or running training test. A finished job is returned unchanged."""
    store = _training_job_store()
    await _owned_training_job(store, job_id)
    job = await store.cancel(get_tenant_context(), job_id)
    if job is None:
        raise _training_job_not_found()
    return training_jobs.public_view(job)


@router.post(
    "/test", dependencies=[Depends(auth), Depends(permissions(P.Workflow.TEST))]
)
async def test_workflow(
    request: Request,
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
        raise HTTPException(
            status_code=400, detail="Input message is required")

    # Redact cardholder data before it enters the workflow engine
    if isinstance(input_data.get("message"), str):
        input_data["message"] = _pii_redactor.redact(input_data["message"])

    try:
        # Determine workflow source
        if workflow_id:
            # Get workflow from database using workflow_id
            db_workflow = await workflow_service.get_by_id(workflow_id)
            if not db_workflow:
                raise HTTPException(
                    status_code=404, detail=f"Workflow with id {workflow_id} not found"
                )

            saved_workflow_id = str(workflow_id)
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
            saved_workflow_id = input_workflow.get("id")
            workflow_config = {
                "id": "test-workflow",
                "nodes": workflow.nodes,
                "edges": workflow.edges,
            }

        async def run() -> dict:
            try:
                thread_id = input_data.get("thread_id", str(uuid.uuid4()))
                start_node_id = input_data.get("human_in_the_loop_node_id")

                # Training would hold this request (and the API) for as long as
                # the fit takes, so it runs as a background job instead. The job
                # runs the same turn (sub-agent routing, registry-managed
                # threads) via run_workflow_test.
                training_nodes = training_jobs.train_model_nodes(
                    workflow_config["nodes"], workflow_config.get("edges") or [], start_node_id
                )
                if training_nodes:
                    return await _queue_training_job(
                        "workflow",
                        training_nodes,
                        {
                            "workflow_config": workflow_config,
                            "input_data": input_data,
                            "start_node_id": start_node_id,
                            "thread_id": thread_id,
                            "workflow_id": saved_workflow_id,
                            "usage_source": "workflow_test",
                        },
                    )

                # Use the new engine approach
                workflow_engine = WorkflowEngine(workflow_config)

                usage_context = WorkflowUsageContext(
                    source="workflow_test", workflow_id=coerce_uuid(saved_workflow_id), defer_capture=True
                )
                return await run_workflow_test(
                    workflow_engine, workflow_config["id"], input_data, thread_id, start_node_id, usage_context
                )
            except (HTTPException, AppException):
                raise
            except Exception as e:
                logger.error(f"Error testing workflow with new engine: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        return await keepalive_json(request, run, name=f"workflow-test:{workflow_config['id']}")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except AppException:
        # Sub-agent session errors carry their own status/key
        raise
    except Exception as e:
        logger.error(f"Error testing workflow with new engine: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/dialog_schema/{node_type}",
    dependencies=[Depends(auth)]
)
async def get_node_dialog_schema(node_type: str):
    if node_type not in SUPPORTED_NODE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported node type: {node_type}. Supported types: {SUPPORTED_NODE_TYPES}",
        )

    return NODE_DIALOG_SCHEMAS[node_type]


@router.post(
    "/test-node", dependencies=[Depends(auth), Depends(permissions("test:workflow"))]
)
async def test_individual_node(request: Request, test_data: Dict[str, Any]):
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

    async def run() -> dict:
        try:
            # Create a unique test ID
            test_id = f"test-{node_type}-{int(time.time())}"

            # Build workflow configuration with single node
            workflow_config = {
                "id": test_id,
                "nodes": [{"id": test_id, "type": node_type, "data": node_config}],
                "edges": [],
            }

            if node_type == training_jobs.TRAIN_MODEL_NODE_TYPE:
                return await _queue_training_job(
                    "node",
                    [node_config],
                    {
                        "workflow_config": workflow_config,
                        "input_data": input_data,
                        "start_node_id": test_id,
                        "usage_source": "node_test",
                    },
                )

            workflow_engine = WorkflowEngine(workflow_config)

            state = await workflow_engine.execute_from_node(
                start_node_id=test_id,
                input_data=input_data,
                usage_context=WorkflowUsageContext(
                    source="node_test",
                    workflow_id=coerce_uuid(workflow_engine.workflow_id),
                    defer_capture=True,
                ),
            )

            return state.format_state_as_response()

        except (HTTPException, AppException):
            raise
        except Exception as e:
            logger.error(f"Error testing {node_type} node: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    return await keepalive_json(request, run, name=f"node-test:{node_type}")


@router.post("/generate-python-template", response_model=Dict[str, Any])
async def generate_python_template(
    test_data: Dict[str, Any],
    llm_provider_svc: LlmProviderService = Injected(LlmProviderService),
    llm_provider: LLMProvider = Injected(LLMProvider),
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
            # Get the default model (first config or default)
            default_model = await llm_provider_svc.get_default()

            # get the llm model
            llm = await llm_provider.get_model(default_model.id)

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
                    len("```python"):
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

# moved to the end to avoid catching other routes like /node_schemas
@router.get(
    "/{workflow_id}",
    response_model=Workflow,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
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
