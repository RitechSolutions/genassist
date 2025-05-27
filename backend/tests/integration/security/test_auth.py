import pytest
import logging

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_me_unauth(client):
    response = client.get("/api/auth/me", headers={"Authorization": "",  "X-API-Key": ""})
    logger.info("test_me_unauth -get response:"+str(response.json()))
    assert response.status_code == 401
    
@pytest.mark.asyncio
async def test_me_auth(client):
    response = client.get("/api/auth/me", headers={"X-API-Key": "test123"})
    logger.info("test_me_auth -get response:"+str(response.json()))
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_user_update(client):
    user_resp = client.get("/api/auth/me", headers={"X-API-Key": "test123"})
    assert user_resp.status_code == 200
    logger.info("test_me_auth -get response:"+str(user_resp.json()))

    update_resp = client.put("/api/user/"+user_resp.json()["id"], headers={"X-API-Key": "test123"}, json={'user_id': user_resp.json()["id"],'notes':'zzz'})
    logger.info("test_me_auth -update response:"+str(update_resp.json()))
    assert update_resp.status_code == 200


@pytest.mark.asyncio
async def test_list_roles(client):
    response = client.get("/api/roles/", headers={"X-API-Key": "test123"})
    assert response.status_code == 200
