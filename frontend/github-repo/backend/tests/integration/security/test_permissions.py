import pytest
import logging
from app.schemas.user import UserRead, UserCreate, UserUpdate

logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def new_prm_data():
    return {
        "name": "test:prm",
        "description": "test prm",
        "is_active": True
    }

@pytest.mark.asyncio
async def test_create_permission(authorized_client, new_prm_data):
    response = authorized_client.post("/api/permissions", json=new_prm_data)
    print(response.json())

    assert response.status_code == 200
    data = response.json()
    print(data)
    assert "id" in data
    assert data["name"] == new_prm_data["name"]
    new_prm_data["id"] = data["id"]  # Store for use in later tests


@pytest.mark.asyncio
async def test_get_permissions(authorized_client):
    response = authorized_client.get("/api/permissions/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)


@pytest.mark.asyncio
async def test_get_prm_by_id(authorized_client, new_prm_data):
    id = new_prm_data["id"]
    response = authorized_client.get(f"/api/permissions/{id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == id


@pytest.mark.asyncio
async def test_update_permission(authorized_client, new_prm_data):
    id = new_prm_data["id"]
    new_prm_data["name"] = "test:prm2"

    response = authorized_client.patch(f"/api/permissions/{id}", json=new_prm_data)
    assert response.status_code == 200
    data = response.json()
    print(data)
    assert data["id"] == id
    assert data["name"] == new_prm_data["name"]

@pytest.mark.asyncio
async def test_delete_permission(authorized_client, new_prm_data):
    id = new_prm_data["id"]
    response = authorized_client.delete(f"/api/permissions/{id}")
    print(response.json())
    assert response.status_code == 200
    assert "deleted" in response.json().get("message", "")

    # Confirm deletion
    get_response = authorized_client.get(f"/api/permissions/{id}")
    assert get_response.status_code == 404
