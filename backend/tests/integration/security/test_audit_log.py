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
