import pytest
import logging

logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def new_api_key_data():
    return {
        "name": "test api key",
        "description": "test api key description",
        "role_ids": []
    }

@pytest.mark.asyncio
async def test_create_api_key(authorized_client, new_api_key_data):
    response = authorized_client.post("/api/api-keys", json=new_api_key_data)
    logger.info(response.json())

    assert response.status_code == 200
    data = response.json()
    assert "key_val" in data
    assert data["name"] == new_api_key_data["name"]
    new_api_key_data["id"] = data["id"]  # Store for use in later tests

@pytest.mark.asyncio
async def test_get_api_keys(authorized_client):
    response = authorized_client.get("/api/api-keys/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)

@pytest.mark.asyncio
async def test_get_api_key_by_id(authorized_client, new_api_key_data):
    id = new_api_key_data["id"]
    response = authorized_client.get(f"/api/api-keys/{id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == id
    assert data["name"] == new_api_key_data["name"]

@pytest.mark.asyncio
async def test_update_api_key(authorized_client, new_api_key_data):
    id = new_api_key_data["id"]
    update_data = {
        "name": "test api key updated",
        "description": "updated description",
        "is_active": 0
    }

    response = authorized_client.patch(f"/api/api-keys/{id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    logger.info(data)
    assert data["id"] == id
    assert data["name"] == update_data["name"]
    assert data["is_active"] == update_data["is_active"]

@pytest.mark.asyncio
async def test_delete_api_key(authorized_client, new_api_key_data):
    id = new_api_key_data["id"]
    response = authorized_client.delete(f"/api/api-keys/{id}")
    logger.info(response.json())
    assert response.status_code == 200
    assert "deleted" in response.json().get("message", "")

    # Confirm deletion
    get_response = authorized_client.get(f"/api/api-keys/{id}")
    assert get_response.status_code == 404 