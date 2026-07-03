import pytest

@pytest.fixture(scope="module")
def new_app_setting_data():
    return {
        "name": "Test Integration",
        "type": "Other",
        "values": {
            "test_key": "test_value",
            "another_key": "another_value"
        },
        "description": "Test app setting for integration tests",
        "is_active": 1
    }

@pytest.mark.asyncio
async def test_create_app_setting(authorized_client, new_app_setting_data):
    response = authorized_client.post("/api/app-settings/", json=new_app_setting_data)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == new_app_setting_data["name"]
    assert data["type"] == new_app_setting_data["type"]
    assert data["values"] == new_app_setting_data["values"]
    new_app_setting_data["id"] = data["id"]

@pytest.mark.asyncio
async def test_get_all_app_settings(authorized_client):
    response = authorized_client.get("/api/app-settings/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)
    if data:
        # Verify structure of returned items
        item = data[0]
        assert "name" in item
        assert "type" in item
        assert "values" in item
        assert isinstance(item["values"], dict)

@pytest.mark.asyncio
async def test_get_app_setting_by_id(authorized_client, new_app_setting_data):
    setting_id = new_app_setting_data["id"]
    response = authorized_client.get(f"/api/app-settings/{setting_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == setting_id
    assert data["name"] == new_app_setting_data["name"]
    assert data["type"] == new_app_setting_data["type"]
    assert data["values"] == new_app_setting_data["values"]

@pytest.mark.asyncio
async def test_get_schemas_endpoint(authorized_client):
    response = authorized_client.get("/api/app-settings/form_schemas")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    # Check that schema types are present
    assert "Zendesk" in data
    assert "WhatsApp" in data
    assert "Gmail" in data
    assert "Microsoft" in data
    assert "Slack" in data
    # Verify schema structure
    if "Zendesk" in data:
        zendesk_schema = data["Zendesk"]
        assert "name" in zendesk_schema
        assert "fields" in zendesk_schema
        assert isinstance(zendesk_schema["fields"], list)

@pytest.mark.asyncio
async def test_schemas_endpoint_includes_salesforce(authorized_client):
    """FR-11: /app-settings/form_schemas exposes the Salesforce credential type."""
    response = authorized_client.get("/api/app-settings/form_schemas")
    assert response.status_code == 200
    data = response.json()
    assert "Salesforce" in data
    salesforce_schema = data["Salesforce"]
    assert "name" in salesforce_schema
    assert "fields" in salesforce_schema
    assert isinstance(salesforce_schema["fields"], list)
    field_names = {field["name"] for field in salesforce_schema["fields"]}
    assert {
        "salesforce_instance_url",
        "salesforce_client_id",
        "salesforce_client_secret",
    } <= field_names


@pytest.mark.asyncio
async def test_create_salesforce_app_setting_round_trips(authorized_client):
    """FR-3: an app-setting of type 'Salesforce' can be created and read back."""
    payload = {
        "name": "My SalesForce Org",
        "type": "Salesforce",
        "values": {
            "salesforce_instance_url": "https://myorg.my.salesforce.com",
            "salesforce_client_id": "client-id",
            "salesforce_client_secret": "client-secret",
        },
        "description": "SalesForce credentials for integration tests",
        "is_active": 1,
    }
    response = authorized_client.post("/api/app-settings/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "Salesforce"
    setting_id = data["id"]

    get_response = authorized_client.get(f"/api/app-settings/{setting_id}")
    assert get_response.status_code == 200
    assert get_response.json()["type"] == "Salesforce"

    # cleanup
    authorized_client.delete(f"/api/app-settings/{setting_id}")


@pytest.mark.asyncio
async def test_update_app_setting(authorized_client, new_app_setting_data):
    setting_id = new_app_setting_data["id"]
    update_payload = {
        "values": {
            "test_key": "updated_value",
            "another_key": "another_value"
        },
        "description": "Updated description",
        "is_active": 0
    }
    response = authorized_client.patch(f"/api/app-settings/{setting_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == setting_id
    assert data["values"] == update_payload["values"]
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
