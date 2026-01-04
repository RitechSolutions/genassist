import pytest
import logging
from app.schemas.user import UserRead, UserCreate, UserUpdate

logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def new_rp_data():
    return {
        "role_id": "",
        "permission_id": "",
    }

@pytest.mark.asyncio
async def test_create_role_perm(authorized_client, new_rp_data):
    #create role first
    role_data = {
        "name": "test role",
        "description": "test role description",
        "is_active": True,
    }

    role_response = authorized_client.post("/api/roles", json=role_data)
    assert role_response.status_code == 200
    role_data = role_response.json()
    assert "id" in role_data
    new_rp_data["role_id"] = role_data["id"]

    #create permission first
    permission_data = {
        "name": "test permission",
        "description": "test permission description",
        "is_active": True,
    }
    permission_response = authorized_client.post("/api/permissions", json=permission_data)
    assert permission_response.status_code == 200
    permission_data = permission_response.json()
    assert "id" in permission_data
    new_rp_data["permission_id"] = permission_data["id"]

    #create role permission
    response = authorized_client.post("/api/role-permissions", json=new_rp_data)
    print(response.json())

    assert response.status_code == 200
    data = response.json()
    print(data)
    assert "id" in data
    new_rp_data["id"] = data["id"]  # Store for use in later tests


@pytest.mark.asyncio
async def test_get_role_perm(authorized_client):
    response = authorized_client.get("/api/role-permissions/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)


@pytest.mark.asyncio
async def test_get_role_perm_by_id(authorized_client, new_rp_data):
    id = new_rp_data["id"]
    response = authorized_client.get(f"/api/role-permissions/{id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == id


@pytest.mark.asyncio
async def test_delete_role_perm(authorized_client, new_rp_data):
    id = new_rp_data["id"]
    response = authorized_client.delete(f"/api/role-permissions/{id}")
    print(response.json())
    assert response.status_code == 200
    assert "deleted" in response.json().get("message", "")

    # Confirm deletion
    get_response = authorized_client.get(f"/api/role-permissions/{id}")
    assert get_response.status_code == 404

    #delete test role   
    role_id = new_rp_data["role_id"]
    role_response = authorized_client.delete(f"/api/roles/{role_id}")
    assert role_response.status_code == 200
    assert "deleted" in role_response.json().get("message", "")
    # Confirm deletion
    get_response = authorized_client.get(f"/api/roles/{role_id}")
    assert get_response.status_code == 404

    #delete test permission
    permission_id = new_rp_data["permission_id"]
    permission_response = authorized_client.delete(f"/api/permissions/{permission_id}")
    assert permission_response.status_code == 200
    assert "deleted" in permission_response.json().get("message", "")
    # Confirm deletion
    get_response = authorized_client.get(f"/api/permissions/{permission_id}")
    assert get_response.status_code == 404
