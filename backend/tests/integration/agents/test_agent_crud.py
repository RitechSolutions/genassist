import json
import logging
import pytest
from app.db.seed.seed_data_config import seed_test_data

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def new_agent_data():
    return {
        "name": "Test Agent",
        "description": "Test description",
        "is_active": True,
        "welcome_message": "Welcome to the test agent!",
        "possible_queries": ["What can you do?", "What can you not do?"],
        "thinking_phrases": ["Thinking...", "Thinking about it..."],
    }


@pytest.mark.asyncio
async def test_get_agents(authorized_client, new_agent_data):
    response = authorized_client.get("/api/genagent/agents/configs")

    data = response.json()
    logger.info(f" test get agents response:{data}")

    assert response.status_code == 200

    assert isinstance(data, list)
    assert any("id" in item for item in data)


@pytest.mark.asyncio
async def test_create_agent(authorized_client, new_agent_data):
    response = authorized_client.post(
        "/api/genagent/agents/configs", json=new_agent_data
    )

    data = response.json()
    logger.info(f" test create agent response:{data}")

    assert response.status_code == 200

    assert "id" in data
    assert data["name"] == new_agent_data["name"]
    new_agent_data["id"] = data["id"]  # Store for use in later tests


@pytest.mark.asyncio
async def test_get_agent_by_id(authorized_client, new_agent_data):
    id = new_agent_data["id"]
    response = authorized_client.get(f"/api/genagent/agents/configs/{id}")

    data = response.json()
    logger.info(f" test get agent by id response:{data}")

    assert response.status_code == 200
    assert data["id"] == id


@pytest.mark.asyncio
async def test_update_agent(authorized_client, new_agent_data):
    id = new_agent_data["id"]
    update = json.loads(json.dumps(new_agent_data))
    update["name"] = "Updated Test Agent"
    del update["id"]

    response = authorized_client.put(f"/api/genagent/agents/configs/{id}", json=update)

    data = response.json()
    print(f" test update agent response:{data}")
    logger.info(f" test update agent response:{data}")

    assert response.status_code == 200
    assert data["id"] == id
    assert data["name"] == update["name"]


@pytest.mark.asyncio
async def test_delete_agent(authorized_client, new_agent_data):
    id = new_agent_data["id"]
    response = authorized_client.delete(f"/api/genagent/agents/configs/{id}")
    assert response.status_code == 200
    assert "deleted" in response.json().get("message", "")

    # Confirm deletion
    get_response = authorized_client.get(f"/api/genagent/agents/configs/{id}")
    assert get_response.status_code == 404
