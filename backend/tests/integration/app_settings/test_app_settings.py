import pytest
from uuid import uuid4

@pytest.fixture(scope="module")
def new_app_setting_data():
    return {
        "key": "TEST_APP_SETTINGS_KEY",
        "value": "true",
        "description": "Enable testing App Settings",
        "is_active": 1,
        "encrypted": 0
    }

@pytest.mark.asyncio
async def test_create_app_setting(authorized_client, new_app_setting_data):
    response = authorized_client.post("/api/app-settings/", json=new_app_setting_data)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["key"] == new_app_setting_data["key"]
    new_app_setting_data["id"] = data["id"]

@pytest.mark.asyncio
async def test_get_all_app_settings(authorized_client):
    response = authorized_client.get("/api/app-settings/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)

@pytest.mark.asyncio
async def test_get_app_setting_by_id(authorized_client, new_app_setting_data):
    setting_id = new_app_setting_data["id"]
    response = authorized_client.get(f"/api/app-settings/{setting_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == setting_id
    assert data["key"] == new_app_setting_data["key"]

@pytest.mark.asyncio
async def test_update_app_setting(authorized_client, new_app_setting_data):
    setting_id = new_app_setting_data["id"]
    update_payload = {
        "value": "false",
        "description": "Disable testing App Settings",
        "is_active": 0
    }
    response = authorized_client.patch(f"/api/app-settings/{setting_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == setting_id
    assert data["value"] == update_payload["value"]
    assert data["description"] == update_payload["description"]
    assert data["is_active"] == update_payload["is_active"]

@pytest.mark.asyncio
async def test_delete_app_setting(authorized_client, new_app_setting_data):
    setting_id = new_app_setting_data["id"]
    response = authorized_client.delete(f"/api/app-settings/{setting_id}")
    assert response.status_code == 204
    assert response.text == ""

    get_response = authorized_client.get(f"/api/app-settings/{setting_id}")
    assert get_response.status_code == 404
