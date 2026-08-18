import pytest

HEADERS = {"X-API-Key": "test123"}


@pytest.mark.asyncio
async def test_list_operators(client):
    response = client.get("/api/operators/", headers=HEADERS)
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list)
    assert body, "seeded operators expected"
    assert "id" in body[0]
    assert "firstName" in body[0]
    assert body[0]["latest_conversation_analysis"] is None


@pytest.mark.asyncio
async def test_paginated_list(client):
    response = client.get("/api/operators/list?limit=5", headers=HEADERS)
    assert response.status_code == 200

    body = response.json()
    assert set(body) >= {"items", "total", "page", "page_size", "total_pages"}
    assert body["page_size"] == 5
    assert body["page"] == 1
    assert len(body["items"]) <= 5
    assert body["items"], "seeded operators expected"

    item = body["items"][0]
    assert "firstName" in item and "lastName" in item
    assert item["operator_statistics"] is not None
    assert "user" not in item
    assert "latest_conversation_analysis" not in item


@pytest.mark.asyncio
async def test_paginated_search_empty(client):
    response = client.get("/api/operators/list?search=zz_no_such_operator", headers=HEADERS)
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_get_operator_by_id(client):
    listing = client.get("/api/operators/", headers=HEADERS)
    assert listing.status_code == 200
    operators = listing.json()
    assert operators, "seeded operators expected"
    operator_id = operators[0]["id"]

    response = client.get(f"/api/operators/{operator_id}", headers=HEADERS)
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == operator_id
    assert body["operator_statistics"] is not None
