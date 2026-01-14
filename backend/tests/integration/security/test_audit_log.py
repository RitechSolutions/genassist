import pytest



@pytest.mark.asyncio
async def test_search_audit_logs_no_filters(client):
    response = client.get("/api/audit-logs/search", headers={"X-API-Key": "test123"})
    assert response.status_code == 200
    data = response.json()
    assert data[0]["table_name"] is not None

@pytest.mark.asyncio
async def test_search_audit_logs_by_table_name(client):
    response = client.get("/api/audit-logs/search", headers={"X-API-Key": "test123"}, params={"table_name": "users"})
    assert response.status_code == 200
    data = response.json()
    assert all(log["table_name"] == "users" for log in data)

@pytest.mark.asyncio
async def test_search_audit_logs_by_action(client):
    response = client.get("/api/audit-logs/search", headers={"X-API-Key": "test123"}, params={"action": "Insert"})
    assert response.status_code == 200
    data = response.json()
    assert all(log["action_name"] == "Insert" for log in data)

@pytest.mark.asyncio
async def test_get_audit_log_by_id(client):
    search_response = client.get("/api/audit-logs/search", headers={"X-API-Key": "test123"})
    assert search_response.status_code == 200
    logs = search_response.json()
    assert len(logs) > 0

    log_id = logs[0]["id"]

    response = client.get(f"/api/audit-logs/{log_id}", headers={"X-API-Key": "test123"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == log_id
    assert data["table_name"] is not None
    assert data["action_name"] is not None

@pytest.mark.asyncio
async def test_get_audit_log_by_invalid_id(client):
    response = client.get("/api/audit-logs/999999", headers={"X-API-Key": "test123"})
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
