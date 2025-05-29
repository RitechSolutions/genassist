import pytest
<<<<<<< HEAD:tests/llm_providers/test_llm_providers.py
=======

from app import settings
>>>>>>> development:tests/integration/llm_providers/test_llm_providers.py


@pytest.fixture(scope="module")
def new_llm_provider_data():
    return {
        "name": "test_provider",
        "llm_model_provider": "openai",
        "connection_data": {
            "api_key": settings.OPENAI_API_KEY
        },
        "is_active": 1,
        "llm_model": "gpt-3.5-turbo"
    }


@pytest.mark.asyncio
async def test_create_llm_provider(authorized_client, new_llm_provider_data):
    response = authorized_client.post("/api/llm-providers/", json=new_llm_provider_data)
    print("test_create_llm_provider - response"+str(response.json()))
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == new_llm_provider_data["name"]
    new_llm_provider_data["id"] = data["id"]  # Store ID for later tests


@pytest.mark.asyncio
async def test_get_all_llm_providers(authorized_client):
    response = authorized_client.get("/api/llm-providers/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)


@pytest.mark.asyncio
async def test_get_llm_provider_by_id(authorized_client, new_llm_provider_data):
    provider_id = new_llm_provider_data["id"]
    response = authorized_client.get(f"/api/llm-providers/{provider_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == provider_id
    assert data["name"] == new_llm_provider_data["name"]


@pytest.mark.asyncio
async def test_update_llm_provider(authorized_client, new_llm_provider_data):
    provider_id = new_llm_provider_data["id"]
    update_payload = {
        "name": "Updated LLM Provider",
        "llm_model": "gpt-4o"
    }
    response = authorized_client.patch(f"/api/llm-providers/{provider_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == provider_id
    assert data["name"] == update_payload["name"]
    assert data["llm_model"] == update_payload["llm_model"]


@pytest.mark.asyncio
async def test_delete_llm_provider(authorized_client, new_llm_provider_data):
    provider_id = new_llm_provider_data["id"]
    response = authorized_client.delete(f"/api/llm-providers/{provider_id}")
    assert response.status_code == 200
    assert "Deleted LLM Provider" in response.json().get("message", "")

    # Confirm deletion
    get_response = authorized_client.get(f"/api/llm-providers/{provider_id}")
    assert get_response.status_code == 404
