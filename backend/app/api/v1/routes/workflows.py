from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Body, Depends, HTTPException, status, Request
import logging
from app.modules.agents.utils import generate_python_function_template
from app.modules.agents.workflow.nodes.python_tool import PythonFunctionNodeProcessor
from app.schemas.workflow import Workflow, WorkflowCreate, WorkflowUpdate
from app.auth.dependencies import auth, permissions
from app.modules.agents.workflow.nodes.knowledge_tool import KnowledgeToolNodeProcessor
from app.modules.agents.workflow import WorkflowRunner
from app.modules.agents.workflow.nodes.slack_tool import SlackMessageNodeProcessor
from app.modules.agents.workflow.nodes.zendesk_tool import ZendeskTicketNodeProcessor
from app.services.workflow import WorkflowService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", 
            response_model=Workflow, 
            status_code=status.HTTP_201_CREATED,
            dependencies=[
                Depends(auth),
                Depends(permissions("create:workflow"))
            ])
async def create_workflow(
    workflow_data: WorkflowCreate,
    request: Request,
    service: WorkflowService = Depends()
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
        version=workflow_data.version,
        user_id=current_user.id
    )
    workflow = await service.create(workflow)
    return workflow


@router.get("/{workflow_id}", 
            response_model=Workflow,
            dependencies=[
                Depends(auth),
                Depends(permissions("read:workflow"))
            ])
async def get_workflow(
    workflow_id: UUID,
    service: WorkflowService = Depends()
):
    """
    Get a workflow by ID
    """
    workflow = await service.get_by_id(workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get("/", 
            response_model=List[Workflow],
            dependencies=[
                Depends(auth),
                Depends(permissions("read:workflow"))
            ])
async def get_workflows(
    service: WorkflowService = Depends()
):
    """
    Get all workflows for the current user
    """
    workflows = await service.get_all()
    return workflows


@router.put("/{workflow_id}", dependencies=[
                Depends(auth),
                Depends(permissions("update:workflow"))
            ],
            response_model=Workflow)
async def update_workflow(
    workflow_id: UUID,
    workflow_data: WorkflowUpdate,
    service: WorkflowService = Depends()
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
    workflow.version = workflow_data.version
    
    
    updated_workflow = await service.update(workflow_id, workflow)
    return updated_workflow


@router.delete("/{workflow_id}", dependencies=[
                Depends(auth),
                Depends(permissions("delete:workflow"))
            ],status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    request: Request,
    service: WorkflowService = Depends()
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
        raise HTTPException(status_code=403, detail="Not authorized to delete this workflow")
    
    await service.delete(workflow_id)


@router.post("/{workflow_id}/execute", 
            dependencies=[
                Depends(auth),
                Depends(permissions("execute:workflow"))
            ])
async def execute_workflow(
    workflow_id: UUID,
    input_data: Dict[str, Any],
):
    """
    Execute a workflow with the given input message
    """
    
    # Get the input message from the request body
    input_message = input_data.get("message", "")
    metadata = input_data.get("metadata", {})
    if not input_message:
        raise HTTPException(status_code=400, detail="Input message is required")
    
    # Run the workflow
    result = await WorkflowRunner.run_workflow(str(workflow_id), user_query=input_message, metadata=metadata)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Unknown error"))
    
    return result

@router.post("/test", 
            dependencies=[
                Depends(auth),
                Depends(permissions("test:workflow"))
            ])
async def test_workflow(
    test_data: Dict[str, Any]
):
    """
    Test a workflow configuration without saving it
    
    Request body should contain:
    - configuration: The workflow configuration
    - message: The input message to test with
    """
    # Extract the configuration and message from the request body
    test_workflow = test_data.get("workflow")
    test_message = test_data.get("message")
    metadata = test_data.get("metadata", {})

    
    logger.info(f"Workflow model: {test_workflow}")
    logger.info(f"Message: {test_message}")
    logger.info(f"Session: {metadata}")
    # Validate inputs
    if not test_workflow:
        raise HTTPException(status_code=400, detail="Workflow model is required")
    
    if not test_message:
        raise HTTPException(status_code=400, detail="Input message is required")
    
    workflow = WorkflowUpdate(**test_workflow)
    # Run the workflow directly from the configuration
    result = await WorkflowRunner.run_from_configuration(workflow, user_query=test_message, metadata=metadata)
    logger.info(f"Result: {result}")
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Unknown error"))
    
    return result 

@router.post("/test-knowledge-tool", 
            dependencies=[
                Depends(auth),
                Depends(permissions("test:workflow"))
            ])
async def test_knowledge_tool(
    test_data: Dict[str, Any],
):
    """
    Test a knowledge tool node with a query
    
    Request body should contain:
    - tool_config: Configuration for the knowledge tool node
    - query: The query to test with
    """
    # Extract the tool configuration and query from the request body
    tool_config = test_data.get("tool_config")
    query = test_data.get("query")
    
    logger.info(f"Tool configuration: {tool_config}")
    logger.info(f"Query: {query}")
    
    # Validate inputs
    if not tool_config:
        raise HTTPException(status_code=400, detail="Knowledge tool configuration is required")
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    

    # Process the query with the knowledge tool
    try:
        # Create a mock node ID
        node_id = "test-knowledge-tool"
        context = None
        # Create a processor for the knowledge tool
        processor = KnowledgeToolNodeProcessor(context, node_id, tool_config)
        # Process the query
        result = await processor.process({"query": query})
        
        # Return the result
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Error testing knowledge tool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 



@router.post("/test-python-function", 
            dependencies=[
                Depends(auth),
                Depends(permissions("test:workflow"))
            ])
async def test_python_function(
    test_data: Dict[str, Any],
):
    """
    Test a python function node with a query
    
    Request body should contain:
    - tool_config: Configuration for the python function node
    - input_data: The input data to test with
    """
    # Extract the tool configuration and query from the request body
    tool_config = test_data.get("tool_config")
    input_parameters = test_data.get("input_params")
    
    logger.info(f"Tool configuration: {tool_config}")
    logger.info(f"Input data: {input_parameters}")
    
    # Validate inputs
    if not tool_config:
        raise HTTPException(status_code=400, detail="Python function configuration is required")
    
    if not input_parameters:
        raise HTTPException(status_code=400, detail="Input data is required")
    

    # Process the query with the knowledge tool
    try:
        # Create a mock node ID
        node_id = "test-python-function"
        context = None
        # Create a processor for the knowledge tool
        processor = PythonFunctionNodeProcessor(context, node_id, tool_config)
        # Process the query
        result = await processor.process(input_data=input_parameters)
        
        # Return the result
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Error testing python function: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 

@router.post(
    "/zendesk-output-message",
    dependencies=[Depends(auth), Depends(permissions("test:workflow"))],
    status_code=status.HTTP_200_OK,
    summary="Test Zendesk ticket creation"
)
async def test_zendesk_ticket(test_data: Dict[str, Any]):
    """
    Only requires subject & description; credentials come from .env via settings.
    """
    missing = [f for f in ("subject", "description") if not test_data.get(f)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields: {missing}"
        )

    processor = ZendeskTicketNodeProcessor(context=None, node_id="zendesk-test", node_data={})
    return await processor.process(input_data=test_data)


@router.post("/generate-python-template", response_model=Dict[str, Any])
async def generate_python_template(
    test_data: Dict[str, Any],
):
    """
    Generate a Python function template based on a tool's parameter schema.
    
    This endpoint generates starter code for a Python function tool based on
    the parameters schema provided. It includes proper parameter extraction,
    type handling, and default values.
    """
    try:
        parameters_schema = test_data.get("parameters_schema", {})
        logger.info(f"Parameters schema: {parameters_schema}")
        
        # Generate code template based on parameters
        template = generate_python_function_template(parameters_schema)
        
        return {"template": template}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Python template: {str(e)}")


@router.post("/slack-output-message", 
            dependencies=[
                Depends(auth),
                Depends(permissions("test:workflow"))
            ])
async def test_slack_data(
    test_data: Dict[str, Any],
):
    """
    Test a slack message to a channel
    
    """
    # Extract the tool configuration and query from the request body
    
    slack_token = test_data.get("slack_token")
    slack_channel = test_data.get("slack_channel")
    slack_message = test_data.get("slack_message")

    
    # logger.info(f"Slack Token: {slack_token}")
    logger.info(f"Slack Channel: {slack_channel}")
    logger.info(f"Slack Message:  {slack_message}")
    
    # Validate inputs
    if not slack_channel:
        raise HTTPException(status_code=400, detail="Slack Channel is required")
    
    if not slack_message:
        raise HTTPException(status_code=400, detail="Slack Message is required")
    

    # Process the query with the knowledge tool
    try:
        # Create a mock node ID
        node_id = "slack-output-message"
        context = None
        # Create a processor for the knowledge tool
        processor = SlackMessageNodeProcessor(context, node_id, {})
        
        result = await processor.process(input_data={"text": slack_message,"channel":slack_channel,"token":slack_token})

        # Return the result
        if not result["data"]["ok"]:
            raise HTTPException(status_code=result["status"], detail=result)
        
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Error testing Slack Message function: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 