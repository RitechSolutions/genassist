import json
import logging
import pytest
import os
import uuid

from app.db.seed.seed_data_config import seed_test_data
from app.schemas.agent_tool import ApiConfig
from app.schemas.workflow import Workflow, WorkflowCreate

logger = logging.getLogger(__name__)

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

#@pytest.mark.skip(reason="Disabled temporarily #TODO: fix this by creating a workflow with proper nodes")
@pytest.mark.asyncio
async def test_create_agent_with_tools_and_kb(authorized_client, new_knowledge_base_data):

    # Create knowledge base
    kb_response = authorized_client.post("/api/genagent/knowledge/items", json=new_knowledge_base_data)
    if kb_response.status_code != 200:
        logger.info("Knowledge base creation failed with status code:", kb_response.status_code)
        logger.info("Error response:", kb_response.json())
    assert kb_response.status_code == 200
    kb_id = kb_response.json()["id"]

    # Create agent configuration
    agent_id = str(uuid.uuid4())
    agent_name = f"test_support_agent_{agent_id[:8]}"
    agent_data = {
        "name": agent_name,
        "description": "AI assistant specialized in providing product support and answering customer queries. Use tools and knowledge base to assist. Call the tools only when necessary.",
        "welcome_message": "Welcome to the test agent!",
        "possible_queries": ["What can you do?", "What can you not do?"],
        "is_active": False  # Start as inactive
    }

    agentsResp = authorized_client.get("/api/genagent/agents/configs/")
    print("Current agents:"+str(agentsResp.json()))
    #agent_data["workflow_id"] = agentsResp.json()[0]["workflow_id"]

    sample_wf = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/test_wf_data.json'

    from pathlib import Path
    file_path = Path(filename)
    json_str = file_path.read_text()
    json_str = json_str.replace("KNOWLEDGEBASE_ID",kb_id)
    
    sample_wf = json.loads(json_str)

    wf_nodes = sample_wf["nodes"]
    wf_edges = sample_wf["edges"]

    #print(f"nodes: {wf_nodes}")
    #print(f"edges: {wf_edges}")

    wf_data = WorkflowCreate(name=agent_name, 
                             description=f"Test agent workflow for {agent_name}",
                             nodes=wf_nodes,
                             edges=wf_edges,
                             version="1.0")
    
    # Create wf
    wf_response = authorized_client.post("/api/genagent/workflow", json=wf_data.dict())
    if wf_response.status_code not in (200, 201):
        logger.info(f"Error response in agent creation: {wf_response.json()}")
    assert wf_response.status_code in (200, 201)
    wf_id = wf_response.json()["id"]
    logger.info(f"Created wf with ID: {wf_id}")

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

    # Create a thread ID for the conversation
    thread_id = str(uuid.uuid4())

    # Test the agent with a question about both product features and currency conversion
    question = "What are the system requirements for your product?"

    test_data = {
        "message": question,
        "session": {
            "base_url":"api.restful-api.dev",
            "thread_id":thread_id,
            "user_id":"test_user_id",
            "user_name":"test_user_name"
        },
        "workflow": wf_response.json()
    }

    #response = authorized_client.post(f"/api/genagent/agents/{agent_id}/query/{thread_id}", json={"query": question})
    response = authorized_client.post(f"/api/genagent/workflow/test", json=test_data)
    if response.status_code != 200:
        logger.info("Agent query failed with status code:", response.status_code)
        logger.info("Error response:", response.json())
    assert response.status_code == 200
    response_data = response.json()
    logger.info("Agent q1:"+str(response_data))

    # Verify response contains relevant information
    assert "ram" in response_data["output"].lower() or "storage" in response_data["output"].lower() or "requirements" in response_data["output"].lower()

    question2 = "What are the available products?"
    test_data2 = {
        "message": question2,
        "session": {
            "base_url":"api.restful-api.dev",
            "thread_id":thread_id,
            "user_id":"test_user_id",
            "user_name":"test_user_name"
        },
        "workflow": wf_response.json()
    }
    #response = authorized_client.post(f"/api/genagent/agents/{agent_id}/query/{thread_id}", json={"query": question})
    response = authorized_client.post(f"/api/genagent/workflow/test", json=test_data2)
    if response.status_code != 200:
        logger.info("Agent query failed with status code:", response.status_code)
        logger.info("Error response:", response.json())
    assert response.status_code == 200
    response_data = response.json()
    logger.info("Agent q2"+str(response_data))
    assert "ipad" in response_data["output"].lower()

    # Cleanup
    authorized_client.delete(f"/api/genagent/knowledge/items/{kb_id}")
    authorized_client.delete(f"/api/genagent/agents/configs/{agent_id}")
    authorized_client.delete(f"/api/genagent/workflow/{wf_id}")
