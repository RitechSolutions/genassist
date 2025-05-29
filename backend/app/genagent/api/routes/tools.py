from fastapi import APIRouter, HTTPException, Depends, Body, Path, status
from typing import List, Dict, Any

from app.genagent.agents.utils import generate_python_function_template, validate_params_against_schema
from app.genagent.services.tool_service import ToolService
from app.genagent.core.dependencies import get_tool_service
from app.genagent.agents.tools import PythonToolImplementation
from app.genagent.models.tool import ParameterSchema, ToolConfig

router = APIRouter()

@router.get("/", response_model=List[ToolConfig], status_code=status.HTTP_200_OK)
async def get_all_tools(
    tool_service: ToolService = Depends(get_tool_service)
):
    """Get all tools"""
    return await tool_service.get_all_tools()

@router.get("/{tool_id}", response_model=ToolConfig, status_code=status.HTTP_200_OK)
async def get_tool_by_id(
    tool_id: str = Path(..., description="The ID of the tool to retrieve"),
    tool_service: ToolService = Depends(get_tool_service)
):
    """Get a specific tool by ID"""
    tool = await tool_service.get_tool_by_id(tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found"
        )
    return tool

@router.post("/", response_model=ToolConfig, status_code=status.HTTP_201_CREATED)
async def create_tool(
    tool: ToolConfig = Body(..., description="The tool configuration to create"),
    tool_service: ToolService = Depends(get_tool_service)
):
    """Create a new tool"""
    created_tool = await tool_service.create_tool(tool)
    if not created_tool:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create tool. It might have invalid data or an ID that already exists."
        )
    return created_tool

@router.put("/{tool_id}", response_model=ToolConfig, status_code=status.HTTP_200_OK)
async def update_tool(
    tool_id: str = Path(..., description="The ID of the tool to update"),
    tool: ToolConfig = Body(..., description="The updated tool configuration"),
    tool_service: ToolService = Depends(get_tool_service)
):
    """Update an existing tool"""
    updated_tool = await tool_service.update_tool(tool_id, tool)
    if not updated_tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found or update failed"
        )
    return updated_tool

@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: str = Path(..., description="The ID of the tool to delete"),
    tool_service: ToolService = Depends(get_tool_service)
):
    """Delete a tool"""
    success = await tool_service.delete_tool(tool_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found"
        )

@router.post("/python/test", response_model=Dict[str, Any])
async def test_python_code(
    request: Dict[str, Any] = Body(...)
):
    """
    Test Python code execution without creating a tool.
    
    This endpoint allows testing Python code with parameters
    before saving it as a permanent tool.
    """
    try:
        code = request.get("code")
        params = request.get("params", {})
        
        if not code:
            raise HTTPException(status_code=400, detail="Python code is required")
        
        # Create a temporary tool config
        tool_config = {
            "id": "temp_test_tool",
            "type": "python",
            "code": code
        }
        
        # Execute the Python code using the PythonToolImplementation
        python_tool = PythonToolImplementation(tool_config)
        result = python_tool._execute_python_code(code, params)
        
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing Python code: {str(e)}")

@router.post("/python/generate-template", response_model=Dict[str, Any])
async def generate_python_template(
    request: Dict[str, Any] = Body(...)
):
    """
    Generate a Python function template based on a tool's parameter schema.
    
    This endpoint generates starter code for a Python function tool based on
    the parameters schema provided. It includes proper parameter extraction,
    type handling, and default values.
    """
    try:
        parameters_schema = request.get("parameters_schema", {})
        
        # Generate code template based on parameters
        template = generate_python_function_template(parameters_schema)
        
        return {"template": template}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Python template: {str(e)}")


@router.post("/python/test-with-schema", response_model=Dict[str, Any])
async def test_python_code_with_schema(
    request: Dict[str, Any] = Body(...)
):
    """
    Test Python code execution with parameter schema validation.
    
    This endpoint allows testing Python code with parameters validated
    against a provided schema, similar to how they would be processed in an agent.
    """
    try:
        code = request.get("code")
        params = request.get("params", {})
        parameters_schema = request.get("parameters_schema", {})
        print(parameters_schema)
        
        if not code:
            raise HTTPException(status_code=400, detail="Python code is required")
        
        # Create a temporary tool config
        tool_config = {
            "id": "temp_test_tool",
            "name": "Test Tool",
            "description": "This is a test tool",
            "type": "function",
            "code": code,
            "parameters_schema": parameters_schema
        }
        tool_config = ToolConfig(**tool_config)
        
        # Execute the Python code using the PythonToolImplementation
        python_tool = PythonToolImplementation(tool_config)
 
        # Validate parameters against schema
        validated_params = validate_params_against_schema(params, parameters_schema)
        
        # Execute code with validated parameters
        result = python_tool._execute_python_code(code, validated_params)
        
        return {
            "result": result,
            "original_params": params,
            "validated_params": validated_params
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing Python code: {str(e)}")
        
