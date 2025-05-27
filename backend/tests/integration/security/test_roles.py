import pytest
import logging
from app.schemas.role import RoleRead, RoleCreate, RoleUpdate

logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def new_role_data():
    return {
        "name": "test role",
        "description": "test role description",
        "is_active": True,
    }

@pytest.mark.asyncio
async def test_create_role(authorized_client, new_role_data):

    response = authorized_client.post("/api/roles", json=new_role_data)
    print(response.json())

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == new_role_data["name"]
    new_role_data["id"] = data["id"]  # Store for use in later tests


@pytest.mark.asyncio
async def test_get_users(authorized_client):
    response = authorized_client.get("/api/roles/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)


@pytest.mark.asyncio
async def test_get_role_by_id(authorized_client, new_role_data):
    id = new_role_data["id"]
    response = authorized_client.get(f"/api/roles/{id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == id


@pytest.mark.asyncio
async def test_update_role(authorized_client, new_role_data):
    id = new_role_data["id"]
    new_role_data["name"] = "test role updated"

    response = authorized_client.patch(f"/api/roles/{id}", json=new_role_data)
    assert response.status_code == 200
    data = response.json()
    print(data)
    assert data["id"] == id
    assert data["name"] == new_role_data["name"]

@pytest.mark.asyncio
async def test_delete_role(authorized_client, new_role_data):
    id = new_role_data["id"]
    response = authorized_client.delete(f"/api/roles/{id}")
    print(response.json())
    assert response.status_code == 200
    assert "deleted" in response.json().get("message", "")

    # Confirm deletion
    get_response = authorized_client.get(f"/api/roles/{id}")
    assert get_response.status_code == 404
