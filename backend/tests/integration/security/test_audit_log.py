import pytest
import json



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


@pytest.mark.asyncio
async def test_audit_log_insert_payload_includes_values_but_redacts_secrets(client):
    search_response = client.get(
        "/api/audit-logs/search",
        headers={"X-API-Key": "test123"},
        params={"table_name": "users", "action": "Insert"},
    )
    assert search_response.status_code == 200
    logs = search_response.json()
    assert len(logs) > 0

    log_id = logs[0]["id"]
    detail_response = client.get(
        f"/api/audit-logs/{log_id}",
        headers={"X-API-Key": "test123"},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()

    payload = json.loads(detail.get("json_changes") or "{}")
    assert "fields" in payload
    assert "values" in payload
    assert isinstance(payload["values"], dict)

    # Make sure we have at least one value and that sensitive fields are redacted.
    assert len(payload["values"].keys()) > 0
    if "hashed_password" in payload["values"]:
        assert payload["values"]["hashed_password"] == "[REDACTED]"
    if "email" in payload["values"]:
        assert payload["values"]["email"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_audit_log_update_redacts_only_sensitive_substrings_in_text_fields(client):
    """
    Free-form text fields (message/text/text_search) should keep surrounding context
    and redact only the sensitive substrings (e.g. emails/tokens).
    """
    search_response = client.get(
        "/api/audit-logs/search",
        headers={"X-API-Key": "test123"},
        params={"action": "Update"},
    )
    assert search_response.status_code == 200
    logs = search_response.json()
    assert len(logs) > 0

    # Find any update log that contains a text-like field diff.
    candidate_id = None
    for log in logs:
        changes = json.loads(log.get("json_changes") or "{}")
        if any(k in changes for k in ("text", "message", "text_search")):
            candidate_id = log["id"]
            break

    # If the dataset doesn't include such an update, skip (keeps test suite stable).
    if candidate_id is None:
        pytest.skip("No audit-log update entries with text/message/text_search diffs found")

    detail_response = client.get(
        f"/api/audit-logs/{candidate_id}",
        headers={"X-API-Key": "test123"},
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    changes = json.loads(detail.get("json_changes") or "{}")

    for field in ("text", "message", "text_search"):
        if field not in changes:
            continue
        old_val = changes[field].get("old")
        new_val = changes[field].get("new")
        # If there is an email/token/etc in the value, it should be partially redacted.
        for val in (old_val, new_val):
            if isinstance(val, str) and ("@" in val or "eyJ" in val):
                assert "[REDACTED]" in val
                assert val != "[REDACTED]"
