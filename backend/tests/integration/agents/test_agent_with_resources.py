import logging
import pytest
import os
import uuid

from app.db.seed.seed_data_config import seed_test_data
from app.schemas.agent_tool import ApiConfig

logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def new_tool_data():
    tool_id = str(uuid.uuid4())
    return {
        "id": tool_id,
        "name": f"test_get_products_{tool_id[:8]}",
        "description": "Get list of products from the API",
        "type": "api",
        "api_config": ApiConfig(
            endpoint="https://api.restful-api.dev/objects",
            method="GET",
            headers={"Content-Type": "application/json"},
            query_params={},
            body={}
        ).model_dump(),
        "parameters_schema": {
        }
    }

@pytest.fixture(scope="module")
def new_knowledge_base_data():
    kb_id = str(uuid.uuid4())
    return {
        "name": f"test_product_docs_{kb_id[:8]}",
        "description": "Technical documentation for our products",
        "type": "file",
        "source": "internal",
        "content": """Product Documentation

1. Core Features
- Real-time audio processing
- AI-powered transcription
- Speaker diarization
- Sentiment analysis
- Custom reporting

2. System Requirements
- Operating System: Windows 10+, macOS 10.15+, Linux
- RAM: 8GB minimum, 16GB recommended
- Storage: 20GB free space
- Internet connection required

3. API Integration
- RESTful API endpoints
- WebSocket support for real-time updates
- OAuth 2.0 authentication
- Rate limiting: 100 requests per minute

4. Security Features
- End-to-end encryption
- Role-based access control
- Audit logging
- Data retention policies

5. Support Resources
- Online documentation
- API reference
- Sample code repositories
- Technical support portal""",
        "file_path": None,
        "file_type": "text",
        "file": None,
        "vector_store": {"config": "default"},
        "rag_config": {
            "enabled": True,
            "vector_db": {"enabled": True},
            "graph_db": {"enabled": False},
            "light_rag": {"enabled": False}
        },
        "extra_metadata": {"category": "technical", "version": "2.1"},
        "embeddings_model": "text-embedding-ada-002"
    }

@pytest.mark.skip(reason="Disabled temporarily #TODO: fix this by creating a workflow with proper nodes")
async def test_create_agent_with_tools_and_kb(authorized_client, new_tool_data, new_knowledge_base_data):
    # Create tool
    tool_response = authorized_client.post("/api/genagent/tools", json=new_tool_data)
    if tool_response.status_code != 201:
        logger.info("Tool creation failed with status code:", tool_response.status_code)
        logger.info("Error response:", tool_response.json())
    assert tool_response.status_code == 201
    tool_id = tool_response.json()["id"]

    # Create knowledge base
    kb_response = authorized_client.post("/api/genagent/knowledge/items", json=new_knowledge_base_data)
    if kb_response.status_code != 200:
        logger.info("Knowledge base creation failed with status code:", kb_response.status_code)
        logger.info("Error response:", kb_response.json())
    assert kb_response.status_code == 200
    kb_id = kb_response.json()["id"]

    # Create agent configuration
    agent_id = str(uuid.uuid4())
    agent_data = {
        "name": f"test_support_agent_{agent_id[:8]}",
        "description": "AI assistant specialized in providing product support and answering customer queries. Use tools and knowledge base to assist. Call the tools only when necessary.",
        "welcome_message": "Welcome to the test agent!",
        "possible_queries": ["What can you do?", "What can you not do?"],
        "workflow_id": "",
        "is_active": False  # Start as inactive
    }

    agentsResp = authorized_client.get("/api/genagent/agents/configs/")
    print("Current agents:"+str(agentsResp.json()))
    agent_data["workflow_id"] = agentsResp.json()[0]["workflow_id"]

    # Create agent
    agent_response = authorized_client.post("/api/genagent/agents/configs", json=agent_data)
    if agent_response.status_code != 200:
        logger.info(f"Error response in agent creation: {agent_response.json()}")
    assert agent_response.status_code == 200
    agent_id = agent_response.json()["id"]
    logger.info(f"Created agent with ID: {agent_id}")
    
    # Initialize agent using the /switch endpoint
    switch_response = authorized_client.post(f"/api/genagent/agents/switch/{agent_id}")
    if switch_response.status_code != 200:
        logger.info(f"Error response in switch agent: {switch_response.json()}")
    assert switch_response.status_code == 200

    # Wait for the agent to be fully initialized
    # max_retries = 10
    # retry_delay = 1
    # for attempt in range(max_retries):
    #     # Check if the agent is active
    #     agent_config = authorized_client.get(f"/api/genagent/agents/configs/{agent_id}").json()
    #     if agent_config["is_active"]:
    #         # Also check if the agent is initialized in the registry
    #         registry_check = authorized_client.get(f"/api/genagent/agents/status/{agent_id}")
    #         if registry_check.status_code == 200 and registry_check.json().get("initialized", False):
    #             break
    #     print(f"Waiting for agent initialization (attempt {attempt + 1}/{max_retries})...")
    #     await asyncio.sleep(retry_delay)
    # else:
    #     raise AssertionError("Agent failed to become active and initialized after maximum retries")

    # Create a thread ID for the conversation
    thread_id = str(uuid.uuid4())

    # Test the agent with a question about both product features and currency conversion
    question = "What are the system requirements for your product?"
    response = authorized_client.post(f"/api/genagent/agents/{agent_id}/query/{thread_id}", json={"query": question})
    if response.status_code != 200:
        logger.info("Agent query failed with status code:", response.status_code)
        logger.info("Error response:", response.json())
    assert response.status_code == 200
    response_data = response.json()
    logger.info("Agent q1:"+str(response_data))

    # Verify response contains relevant information
    assert "ram" in response_data["response"].lower() or "storage" in response_data["response"].lower() or "requirements" in response_data["response"].lower()

    question = "What are the available products?"
    response = authorized_client.post(f"/api/genagent/agents/{agent_id}/query/{thread_id}", json={"query": question})
    if response.status_code != 200:
        logger.info("Agent query failed with status code:", response.status_code)
        logger.info("Error response:", response.json())
    assert response.status_code == 200
    response_data = response.json()
    logger.info("Agent q2"+str(response_data))
    assert "ipad" in response_data["response"].lower()

    # Cleanup
    authorized_client.delete(f"/api/genagent/tools/{tool_id}")
    authorized_client.delete(f"/api/genagent/knowledge/items/{kb_id}")
    authorized_client.delete(f"/api/genagent/agents/configs/{agent_id}")
