from fastapi import APIRouter, Depends, Body, HTTPException, status
from typing import Any, Dict, List
from uuid import UUID
from app.auth.dependencies import auth, permissions
from app.modules.agents.tools import PythonToolImplementation
from app.modules.agents.utils import generate_python_function_template, validate_params_against_schema
from app.services.agent_tool import ToolService
from app.schemas.agent_tool import ToolConfigBase, ToolConfigRead

router = APIRouter()

@router.get("/", response_model=List[ToolConfigRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:tool"))
    ])
async def get_all_tools(tool_service: ToolService = Depends()):
    return await tool_service.get_all()


@router.get("/{tool_id}", response_model=ToolConfigRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:tool"))
    ])
async def get_tool_by_id(tool_id: UUID, tool_service: ToolService = Depends()):
    return await tool_service.get_by_id(tool_id)

@router.post("/", response_model=ToolConfigRead, status_code=status.HTTP_201_CREATED,
             dependencies=[
                 Depends(auth),
                 Depends(permissions("create:tool"))
                 ]
             )
async def create_tool(tool: ToolConfigBase = Body(...), tool_service: ToolService = Depends()):
    return await tool_service.create(tool)


@router.put("/{tool_id}", response_model=ToolConfigRead, dependencies=[
    Depends(auth),
    Depends(permissions("update:tool"))
                 ])
async def update_tool(tool_id: UUID, tool: ToolConfigBase = Body(...), tool_service: ToolService = Depends(), ):
    return await tool_service.update(tool_id, tool)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[
    Depends(auth),
    Depends(permissions("delete:tool"))
    ])
async def delete_tool(tool_id: UUID, tool_service: ToolService = Depends()):
    return await tool_service.delete(tool_id)
<<<<<<< HEAD
=======

>>>>>>> development
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
<<<<<<< HEAD
            "id": "temp_test_tool",
=======
            "id": "00000000-0000-0000-0000-000000000000",
>>>>>>> development
            "name": "Test Tool",
            "description": "This is a test tool",
            "type": "function",
            "code": code,
            "parameters_schema": parameters_schema
        }
        tool_config = ToolConfigRead(**tool_config)
        
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
        

