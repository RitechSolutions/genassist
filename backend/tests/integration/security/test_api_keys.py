import pytest
import logging
from uuid import uuid4

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


@pytest.fixture
def listed_api_key(authorized_client):
    name = f"zz_list_{uuid4().hex[:8]}"
    response = authorized_client.post("/api/api-keys", json={"name": name, "role_ids": []})
    assert response.status_code == 200, response.text
    created = response.json()
    yield created
    authorized_client.delete(f"/api/api-keys/{created['id']}")


@pytest.mark.asyncio
async def test_get_api_keys_paginated(authorized_client, listed_api_key):
    response = authorized_client.get("/api/api-keys/list", params={"limit": 5, "search": listed_api_key["name"]})
    assert response.status_code == 200

    body = response.json()
    assert set(body) >= {"items", "total", "page", "page_size", "total_pages"}
    assert body["page"] == 1 and body["page_size"] == 5 and body["total"] == 1
    assert [item["id"] for item in body["items"]] == [listed_api_key["id"]]

    item = body["items"][0]
    assert "roles" in item and "key_val" not in item and "hashed_value" not in item


@pytest.mark.asyncio
async def test_get_api_keys_paginated_excludes_deleted(authorized_client, listed_api_key):
    authorized_client.delete(f"/api/api-keys/{listed_api_key['id']}")

    body = authorized_client.get("/api/api-keys/list", params={"search": listed_api_key["name"]}).json()
    assert body["total"] == 0 and body["items"] == []
