import logging
import pytest
from uuid import UUID

logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def new_api_tool_data():
    return {
        "name": "Products Tool",
        "description": "Tool to get list of products",
        "type": "api",
        "api_config": {
            "endpoint": "https://api.restful-api.dev/objects",
            "method": "GET",
            "headers": {"Content-Type": "application/json"},
            "query_params": {},
            "body": {}
        },
        "parameters_schema": {
        }
    }

@pytest.fixture(scope="module")
def new_python_tool_data():
    return {
        "name": "Test Python Tool",
        "description": "A test Python tool for testing",
        "type": "function",
        "function_config": {
            "code": """
                    def execute(params):
                        result = f"Hello {params.get('name', 'World')}!"
                        return result
                    """
        },
        "parameters_schema": {
            "name": {
                "type": "string",
                "description": "Name to greet"
            }
        }
    }

@pytest.mark.asyncio
async def test_create_api_tool(authorized_client, new_api_tool_data):
    response = authorized_client.post("/api/genagent/tools", json=new_api_tool_data)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == new_api_tool_data["name"]
    assert data["type"] == "api"
    new_api_tool_data["id"] = data["id"]  # Store for use in later tests

@pytest.mark.asyncio
async def test_create_python_tool(authorized_client, new_python_tool_data):
    response = authorized_client.post("/api/genagent/tools", json=new_python_tool_data)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == new_python_tool_data["name"]
    assert data["type"] == "function"
    new_python_tool_data["id"] = data["id"]  # Store for use in later tests

@pytest.mark.asyncio
async def test_get_all_tools(authorized_client):
    response = authorized_client.get("/api/genagent/tools/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)

@pytest.mark.asyncio
async def test_get_tool_by_id(authorized_client, new_api_tool_data):
    tool_id = new_api_tool_data["id"]
    response = authorized_client.get(f"/api/genagent/tools/{tool_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == tool_id
    assert data["name"] == new_api_tool_data["name"]

@pytest.mark.asyncio
async def test_update_tool(authorized_client, new_api_tool_data):
    tool_id = new_api_tool_data["id"]
    updated_data = new_api_tool_data.copy()
    updated_data["name"] = "Updated Test API Tool"
    updated_data["description"] = "Updated description"

    response = authorized_client.put(f"/api/genagent/tools/{tool_id}", json=updated_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == tool_id
    assert data["name"] == updated_data["name"]
    assert data["description"] == updated_data["description"]

@pytest.mark.asyncio
async def test_get_nonexistent_tool(authorized_client):
    nonexistent_id = "00000000-0000-0000-0000-000000000000"
    response = authorized_client.get(f"/api/genagent/tools/{nonexistent_id}")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_update_nonexistent_tool(authorized_client, new_api_tool_data):
    nonexistent_id = "00000000-0000-0000-0000-000000000000"
    response = authorized_client.put(f"/api/genagent/tools/{nonexistent_id}", json=new_api_tool_data)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_tool_python_gen_template(authorized_client):
    parameters_schema = {
        "name": {
            "type": "string",
            "description": "Name to greet"
        }
    }

    response = authorized_client.post("/api/genagent/tools/python/generate-template", json=parameters_schema)
    data = response.json()
    logger.info(f"generate-template response: {data}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_tool_python_test(authorized_client):
    code_params = {
        "code": 
"""
result = f"Hello {params.get('name', 'World')}!"
""",
        "params": {
            "name": "Test"
        }
    }

    response = authorized_client.post("/api/genagent/tools/python/test", json=code_params)
    assert response.status_code == 200
    data = response.json()
    logger.info(f"python test response: {data}")


@pytest.mark.asyncio
async def test_tool_python_test_with_schema(authorized_client):
    code_params = {
        "code": 
"""
result = f"Hello {params.get('name', 'World')}!"
""",
        "params": {
            "name": "Test"
        },
        "parameters_schema": {
            "name": {
                "type": "string",
                "description": "Name to greet"
            }
        }
    }

    response = authorized_client.post("/api/genagent/tools/python/test-with-schema", json=code_params)
    data = response.json()
    logger.info(f"python test with schema response: {data}")
    assert response.status_code == 200

#sample template
"""
    {'template': '# Generated Python function template
     # Access parameters via the \'params\' dictionary
     # # Store your result in the \'result\' variable
     # 
     # # Import any additional libraries you need
     # # import json
     # # import requests
     # # import datetime
     # 
     # try:
     #     # Extract parameters with type validation
     #     # No parameters defined in schema
     #     pass
     #     # Your code logic here - example using the parameters:
     #     result = \'Successfully executed function with no parameters\'
     # 
     # except Exception as e:
     #     # Handle any errors
     #     import traceback
     #     result = f"Error processing parameters: {str(e)}\\n{traceback.format_exc()}"
     # '}"""