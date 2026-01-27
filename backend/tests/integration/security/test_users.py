import pytest
import logging
import os

from app.schemas.filter import BaseFilterModel
from app.schemas.user import UserRead, UserCreate, UserUpdate

logger = logging.getLogger(__name__)

# Test-only credentials - these are intentionally simple for integration testing
# and are never used in production. They can be overridden via environment variables.
TEST_USER_USERNAME = os.environ.get('TEST_INT_USER_USERNAME', 'test_user')
TEST_USER_EMAIL = os.environ.get('TEST_INT_USER_EMAIL', 'test@test.com')
TEST_USER_PASSWORD = os.environ.get('TEST_INT_USER_PASSWORD', 'test_password')  # nosec B105 - test credential

@pytest.fixture(scope="module")
def new_user_data():
    return {
        "username": TEST_USER_USERNAME,
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "notes": "Test user for API testing",
        "is_active": True,
        "user_type_id": "",
    }

@pytest.mark.asyncio
async def test_user_me(client):
    user_resp = client.get("/api/auth/me", headers={"X-API-Key": "test123"})
    assert user_resp.status_code == 200


@pytest.mark.asyncio
async def test_create_user(authorized_client, new_user_data):
    response = authorized_client.get("/api/user-type/")
    assert response.status_code == 200
    types = response.json()

    new_user_data["user_type_id"] = types[0]["id"]

    response = authorized_client.get("/api/roles/")
    assert response.status_code == 200
    roles = response.json()
    admin_role = next((role for role in roles if role.get("name") == "admin"), None)
    new_user_data["role_ids"] = [admin_role["id"]]

    response = authorized_client.post("/api/user", json=new_user_data)
    print("create_user_response")
    print(response.json())

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["email"] == new_user_data["email"]
    new_user_data["id"] = data["id"]  # Store for use in later tests


@pytest.mark.asyncio
async def test_get_users(authorized_client):
    response = authorized_client.get("/api/user/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)


@pytest.mark.asyncio
async def test_get_user_by_id(authorized_client, new_user_data):
    id = new_user_data["id"]
    response = authorized_client.get(f"/api/user/{id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == id


@pytest.mark.asyncio
async def test_update_user(authorized_client, new_user_data):
    id = new_user_data["id"]
    new_user_data["email"] = "test2@test.com"

    response = authorized_client.put(f"/api/user/{id}", json=new_user_data)
    assert response.status_code == 200
    data = response.json()
    print(data)
    assert data["id"] == id
    assert data["email"] == new_user_data["email"]
