from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.db.models.workflow import WorkflowModel
from app.modules.agents.data.datasource_service import AgentDataSourceService
from app.modules.agents.workflow.builder import WorkflowContext
from app.schemas.workflow import Workflow, WorkflowCreate, WorkflowUpdate
from app.repositories.workflow import WorkflowRepository
from app.auth.dependencies import auth, permissions
from app.modules.agents.workflow.nodes.knowledge_tool import KnowledgeToolNodeProcessor
from app.modules.agents.workflow import WorkflowRunner
from app.services.agent_knowledge import KnowledgeBaseService

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
    repository: WorkflowRepository = Depends()
):
    """
    Create a new workflow
    """
    current_user = request.state.user
    workflow = WorkflowModel(
        name=workflow_data.name,
        description=workflow_data.description,
        nodes=workflow_data.nodes,
        edges=workflow_data.edges,
        version=workflow_data.version,
        user_id=current_user.id
    )
    workflow = await repository.create(workflow)
    return workflow


@router.get("/{workflow_id}", 
            response_model=Workflow,
            dependencies=[
                Depends(auth),
                Depends(permissions("read:workflow"))
            ])
async def get_workflow(
    workflow_id: UUID,
    request: Request,
    repository: WorkflowRepository = Depends()
):
    """
    Get a workflow by ID
    """
    current_user = request.state.user
    workflow = await repository.get_by_id(workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if the user owns this workflow
    if workflow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this workflow")
    
    return workflow


@router.get("/", 
            response_model=List[Workflow],
            dependencies=[
                Depends(auth),
                Depends(permissions("read:workflow"))
            ])
async def get_workflows(
    request: Request,
    repository: WorkflowRepository = Depends()
):
    """
    Get all workflows for the current user
    """
    # current_user = request.state.user
    workflows = await repository.get_all()
    return workflows


@router.put("/{workflow_id}", dependencies=[
                Depends(auth),
                Depends(permissions("update:workflow"))
            ],
            response_model=Workflow)
async def update_workflow(
    workflow_id: UUID,
    workflow_data: WorkflowUpdate,
    request: Request,
    repository: WorkflowRepository = Depends()
):
    """
    Update a workflow
    """
    logger.info(f"Updating workflow: {workflow_id}")
    logger.info(f"Workflow data: {workflow_data}")
    workflow = await repository.get_by_id(workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    current_user = request.state.user
    # Check if the user owns this workflow
    if workflow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this workflow")
    
    # Update the workflow
    workflow.name = workflow_data.name
    workflow.description = workflow_data.description
    workflow.nodes = workflow_data.nodes
    workflow.edges = workflow_data.edges
    workflow.version = workflow_data.version
    
    
    updated_workflow = await repository.update(workflow)
    return updated_workflow


@router.delete("/{workflow_id}", dependencies=[
                Depends(auth),
                Depends(permissions("delete:workflow"))
            ],status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    request: Request,
    repository: WorkflowRepository = Depends()
):
    """
    Delete a workflow
    """
    current_user = request.state.user
    workflow = await repository.get_by_id(workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if the user owns this workflow
    if workflow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this workflow")
    
    await repository.delete(workflow)


@router.post("/{workflow_id}/execute", 
            dependencies=[
                Depends(auth),
                Depends(permissions("execute:workflow"))
            ])
async def execute_workflow(
    workflow_id: UUID,
    input_data: Dict[str, Any],
    request: Request
):
    """
    Execute a workflow with the given input message
    """
    current_user = request.state.user
    
    # Get the input message from the request body
    input_message = input_data.get("message", "")
    session = input_data.get("session", {})
    if not input_message:
        raise HTTPException(status_code=400, detail="Input message is required")
    
    # Run the workflow
    result = await WorkflowRunner.run_workflow(str(workflow_id), user_query=input_message, metadata=session)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Unknown error"))
    
    return result

@router.post("/test", 
            dependencies=[
                Depends(auth),
                Depends(permissions("test:workflow"))
            ])
async def test_workflow(
    request: Request,
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
    session = test_data.get("session", {})

    
    logger.info(f"Workflow model: {test_workflow}")
    logger.info(f"Message: {test_message}")
    logger.info(f"Session: {session}")
    # Validate inputs
    if not test_workflow:
        raise HTTPException(status_code=400, detail="Workflow model is required")
    
    if not test_message:
        raise HTTPException(status_code=400, detail="Input message is required")
    
    workflow = WorkflowUpdate(**test_workflow)
    # Run the workflow directly from the configuration
    result = await WorkflowRunner.run_from_configuration(workflow, user_query=test_message, metadata=session)
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
    request: Request,
    test_data: Dict[str, Any],
    knowledge_service: KnowledgeBaseService = Depends(),
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
    
    # Check if the configuration is for a knowledge tool
    # if tool_config.get("name") != "knowledge_tool":
    #     raise HTTPException(status_code=400, detail="Configuration is not for a knowledge tool")
    
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
