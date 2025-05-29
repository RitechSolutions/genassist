import pytest
<<<<<<< HEAD:tests/llm_analyst/test_llm_analyst.py
from app.db.seed.seed import seed_test_data
=======
from app.db.seed.seed_data_config import seed_test_data
>>>>>>> development:tests/integration/llm_analyst/test_llm_analyst.py

@pytest.fixture(scope="module")
def new_llm_analyst_data():
    return {
        "name": "Test Analyst",
        "llm_provider_id": seed_test_data.llm_provider_id,
        "prompt": seed_test_data.kpi_analyzer_system_prompt,
        "is_active": 1
    }


@pytest.mark.asyncio
async def test_create_llm_analyst(authorized_client, new_llm_analyst_data):
    response = authorized_client.post("/api/llm-analyst/", json=new_llm_analyst_data)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == new_llm_analyst_data["name"]
    new_llm_analyst_data["id"] = data["id"]  # Store for use in later tests


@pytest.mark.asyncio
async def test_get_all_llm_analysts(authorized_client):
    response = authorized_client.get("/api/llm-analyst/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)


@pytest.mark.asyncio
async def test_get_llm_analyst_by_id(authorized_client, new_llm_analyst_data):
    llm_analyst_id = new_llm_analyst_data["id"]
    response = authorized_client.get(f"/api/llm-analyst/{llm_analyst_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == llm_analyst_id


@pytest.mark.asyncio
async def test_update_llm_analyst(authorized_client, new_llm_analyst_data):
    llm_analyst_id = new_llm_analyst_data["id"]
    update_payload = {
        "name": "Updated Test Analyst",
        "prompt": "Updated prompt"
    }
    response = authorized_client.patch(f"/api/llm-analyst/{llm_analyst_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == llm_analyst_id
    assert data["name"] == update_payload["name"]
    assert data["prompt"] == update_payload["prompt"]


@pytest.mark.asyncio
async def test_delete_llm_analyst(authorized_client, new_llm_analyst_data):
    llm_analyst_id = new_llm_analyst_data["id"]
    response = authorized_client.delete(f"/api/llm-analyst/{llm_analyst_id}")
    assert response.status_code == 200
    assert "has been deleted" in response.json().get("message", "")

    # Confirm deletion
    get_response = authorized_client.get(f"/api/llm-analyst/{llm_analyst_id}")
    assert get_response.status_code == 404
