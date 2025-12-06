import json
import logging
import pytest
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def new_knowledge_base_data():
    return {
        "name": "Test contract kb",
        "description": "Contains contract ",
        "type": "text",
        "source": None,
        "file_path": None,
        "file_type": None,
        "files": [],
        "vector_store": None,
        "rag_config": {
            "enabled": True,
            "vector_db": {"type": "chroma", "enabled": True, "collection_name": ""},
            "graph_db": {"type": "neo4j", "enabled": False},
            "light_rag": {"enabled": True, "search_mode": "mix"},
            "legra": {
                "enabled": True,
                "questions": "Show me development and implementation",
            },
        },
        "extra_metadata": {},
        "embeddings_model": None,
        "legra_finalize": False,
        "last_synced": None,
        "last_sync_status": None,
        "last_sync_error": None,
        "last_file_date": None,
        "sync_schedule": "",
        "sync_active": False,
        "sync_source_id": None,
        "llm_provider_id": None,
        "url": None,
        "id": "f7a0fe33-100a-4fdf-a836-8d1dbbc42370",
    }


@pytest.mark.skip(reason="Test disabled")
@pytest.mark.asyncio
async def test_create_agent_with_tools_and_kb(
    authorized_client, new_knowledge_base_data
):

    # Get the directory of the current test file
    current_dir = Path(__file__).parent

    # Load test_wf_data.json as before
    json_path = current_dir.joinpath("agent_test_data").joinpath("test_wf_data.json")
    json_str = json_path.read_text()

    # Load the .txt file
    txt_path = current_dir.joinpath("agent_test_data").joinpath(
        "2ThemartComInc_19990826_10-12G_EX-10.10_6700288_EX-10.10_Co-Branding Agreement_ Agency Agreement.txt"
    )
    new_knowledge_base_data["content"] = txt_path.read_text()

    # Create knowledge base
    kb_response = authorized_client.post(
        "/api/genagent/knowledge/items", json=new_knowledge_base_data
    )
    if kb_response.status_code != 200:
        logger.info(
            "Knowledge base creation failed with status code: %s",
            kb_response.status_code,
        )
        logger.info("Error response: %s", kb_response.json())
    assert kb_response.status_code == 200

    kb_id = kb_response.json()["id"]

    # Create agent configuration
    agent_data = {
        "name": "Contract agent",
        "description": "Contract agent",
        "is_active": False,
        "welcome_message": "Welcome, I can help you about contract questions.",
        "possible_queries": ["Tell me about the DEVELOPMENT AND IMPLEMENTATION", ""],
    }

    agent_response = authorized_client.post(
        "/api/genagent/agents/configs", json=agent_data
    )
    if agent_response.status_code != 200:
        logger.info(f"Error response in agent creation: {agent_response.json()}")

    assert agent_response.status_code == 200

    agent_id = agent_response.json()["id"]
    workflow_id = agent_response.json()["workflow_id"]
    logger.info(f"Created agent with ID: {agent_id}")

    # load workflow sample json and update the basic workflow of the agent
    sample_wf = json.loads(json_str)

    # set created agent, workflow id and knowledge base
    sample_wf["agent_id"] = agent_id
    sample_wf["id"] = workflow_id
    node = next(
        (n for n in sample_wf["nodes"] if n["data"]["name"] == "Knowledge Base"), None
    )
    if node:
        node["data"]["selectedBases"] = [kb_id]

    # Create wf
    wf_response = authorized_client.post("/api/genagent/workflow", json=sample_wf)
    if wf_response.status_code not in (200, 201):
        logger.info(f"Error response in agent creation: {wf_response.json()}")
    assert wf_response.status_code in (200, 201)
    wf_id = wf_response.json()["id"]
    logger.info(f"Created wf with ID: {wf_id}")

    # Initialize agent using the /switch endpoint
    switch_response = authorized_client.post(f"/api/genagent/agents/switch/{agent_id}")
    if switch_response.status_code != 200:
        logger.info(f"Error response in switch agent: {switch_response.json()}")
    assert switch_response.status_code == 200

    # Create a thread ID for the conversation
    thread_id = str(uuid.uuid4())

    # Test the agent with a question about both product features and currency conversion
    question = "What are the DEVELOPMENT AND IMPLEMENTATION details?"

    test_data = {
        "message": question,
        "metadata": {
            "base_url": "api.restful-api.dev",
            "thread_id": thread_id,
            "user_id": "test_user_id",
            "user_name": "test_user_name",
        },
        "workflow": wf_response.json(),
    }

    response = authorized_client.post("/api/genagent/workflow/test", json=test_data)
    if response.status_code != 200:
        logger.info("Agent query failed with status code: %s", response.status_code)
        logger.info("Error response: %s", response.json())
    assert response.status_code == 200
    response_data = response.json()
    logger.info("Agent q1:" + str(response_data))

    # Verify response contains relevant information
    assert "2TheMart" in response_data["output"]

    # Cleanup
    authorized_client.delete(f"/api/genagent/knowledge/items/{kb_id}")
    authorized_client.delete(f"/api/genagent/agents/configs/{agent_id}")
    authorized_client.delete(f"/api/genagent/workflow/{wf_id}")
