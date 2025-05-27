import pytest
from uuid import uuid4

@pytest.fixture(scope="module")
def new_feature_flag_data():
    return {
        "key": "TEST_FEATURE_FLAG",
        "val": "true",
        "description": "Test feature flag for integration",
        "is_active": 1,
        "encrypted": 0
    }

@pytest.mark.asyncio
async def test_create_feature_flag(authorized_client, new_feature_flag_data):
    response = authorized_client.post("/api/feature-flags/", json=new_feature_flag_data)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["key"] == new_feature_flag_data["key"]
    new_feature_flag_data["id"] = data["id"]

@pytest.mark.asyncio
async def test_get_all_feature_flags(authorized_client):
    response = authorized_client.get("/api/feature-flags/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)

@pytest.mark.asyncio
async def test_get_feature_flag_by_id(authorized_client, new_feature_flag_data):
    flag_id = new_feature_flag_data["id"]
    response = authorized_client.get(f"/api/feature-flags/{flag_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == flag_id
    assert data["key"] == new_feature_flag_data["key"]

@pytest.mark.asyncio
async def test_update_feature_flag(authorized_client, new_feature_flag_data):
    flag_id = new_feature_flag_data["id"]
    update_payload = {
        "val": "off",
        "description": "Updated feature flag",
        "is_active": 0
    }
    response = authorized_client.patch(f"/api/feature-flags/{flag_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == flag_id
    assert data["val"] == update_payload["val"]
    assert data["description"] == update_payload["description"]
    assert data["is_active"] == update_payload["is_active"]

@pytest.mark.asyncio
async def test_delete_feature_flag(authorized_client, new_feature_flag_data):
    flag_id = new_feature_flag_data["id"]
    response = authorized_client.delete(f"/api/feature-flags/{flag_id}")
    assert response.status_code == 204
    assert response.text == ""

    get_response = authorized_client.get(f"/api/feature-flags/{flag_id}")
    assert get_response.status_code == 404
