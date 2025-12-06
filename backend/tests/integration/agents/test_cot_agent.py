import json
import logging
import pytest
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


@pytest.mark.skip(reason="Test disabled")
@pytest.mark.asyncio
async def test_create_and_ask_cot_agent(authorized_client):

    # Get the directory of the current test file
    current_dir = Path(__file__).parent

    json_path = current_dir.joinpath("agent_test_data").joinpath("cot_wf_data.json")
    json_str = json_path.read_text()

    # Create agent configuration
    agent_data = {
        "name": "COT agent",
        "description": "Chain of Thought Agent",
        "is_active": False,
        "welcome_message": "Welcome, I can help you about reasoning and complex queries.",
        "possible_queries": [
            "What are the usual steps in a operator-customer interaction?",
            "",
        ],
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

    # Create wf
    wf_response = authorized_client.post("/api/genagent/workflow", json=sample_wf)
    if wf_response.status_code not in (200, 201):
        logger.info(f"Error response in workflow creation: {wf_response.json()}")
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

    # Test the agent with a question that requires reasoning
    question = "What are the usual steps in a operator-customer interaction?"

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
    logger.info("Agent response:" + str(response_data))

    # Verify response contains relevant information
    assert "customer" in response_data["output"]
    assert "interaction" in response_data["output"]

    # Cleanup
    authorized_client.delete(f"/api/genagent/agents/configs/{agent_id}")
    authorized_client.delete(f"/api/genagent/workflow/{wf_id}")
