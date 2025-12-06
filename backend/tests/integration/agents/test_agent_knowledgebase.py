import logging
import pytest
import os
import tempfile

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def new_knowledge_item_data():
    return {
        "name": "Test Knowledge Base",
        "description": "A test knowledge base item",
        "type": "text",
        "content": "This is a test knowledge base content",
        "rag_config": {
            "vector_db": {"enabled": True},
            "graph_db": {"enabled": False},
            "light_rag": {"enabled": False},
            "legra": {"enabled": True},
        },
    }


@pytest.fixture(scope="module")
def test_file_content():
    return "This is a test file content for knowledge base"


@pytest.fixture(scope="module")
def test_file(test_file_content):
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write(test_file_content)
        f.flush()
        yield f.name
    # Cleanup
    os.unlink(f.name)


@pytest.mark.asyncio
async def test_create_knowledge_item(authorized_client, new_knowledge_item_data):
    response = authorized_client.post(
        "/api/genagent/knowledge/items", json=new_knowledge_item_data
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == new_knowledge_item_data["name"]
    assert data["type"] == "text"
    new_knowledge_item_data["id"] = data["id"]  # Store for use in later tests


@pytest.mark.asyncio
async def test_get_all_knowledge_items(authorized_client):
    response = authorized_client.get("/api/genagent/knowledge/items")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("id" in item for item in data)


@pytest.mark.asyncio
async def test_get_knowledge_item_by_id(authorized_client, new_knowledge_item_data):
    item_id = new_knowledge_item_data["id"]
    response = authorized_client.get(f"/api/genagent/knowledge/items/{item_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["name"] == new_knowledge_item_data["name"]


@pytest.mark.asyncio
async def test_update_knowledge_item(authorized_client, new_knowledge_item_data):
    item_id = new_knowledge_item_data["id"]
    updated_data = new_knowledge_item_data.copy()
    updated_data["name"] = "Updated Test Knowledge Base"
    updated_data["description"] = "Updated description"

    response = authorized_client.put(
        f"/api/genagent/knowledge/items/{item_id}", json=updated_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["name"] == updated_data["name"]
    assert data["description"] == updated_data["description"]


@pytest.mark.skip(reason="Skipping temporarily until is fixed the error")
@pytest.mark.asyncio
async def test_finalize_legra_knowledge_item(
    authorized_client, new_knowledge_item_data
):
    kb_id = new_knowledge_item_data["id"]

    response = authorized_client.post(f"/api/genagent/knowledge/finalize/{kb_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Successfully finalized legra knowledge base."


@pytest.mark.asyncio
async def test_delete_knowledge_item(authorized_client, new_knowledge_item_data):
    item_id = new_knowledge_item_data["id"]
    response = authorized_client.delete(f"/api/genagent/knowledge/items/{item_id}")
    data = response.json()
    logger.info(f"Delete response: {data}")
    assert response.status_code == 200

    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_upload_file(authorized_client, test_file):
    with open(test_file, "rb") as f:
        response = authorized_client.post(
            "/api/genagent/knowledge/upload",
            files=[("files", ("test.txt", f, "text/plain"))],
        )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert "filename" in data[0]
    assert "original_filename" in data[0]
    assert "file_path" in data[0]


@pytest.mark.asyncio
async def test_get_nonexistent_knowledge_item(authorized_client):
    nonexistent_id = "00000000-0000-0000-0000-000000000000"
    response = authorized_client.get(f"/api/genagent/knowledge/items/{nonexistent_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_nonexistent_knowledge_item(
    authorized_client, new_knowledge_item_data
):
    nonexistent_id = "00000000-0000-0000-0000-000000000000"
    response = authorized_client.put(
        f"/api/genagent/knowledge/items/{nonexistent_id}", json=new_knowledge_item_data
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_knowledge_item(authorized_client):
    nonexistent_id = "00000000-0000-0000-0000-000000000000"
    response = authorized_client.delete(
        f"/api/genagent/knowledge/items/{nonexistent_id}"
    )
    logger.info(f"Delete nonexistent response: {response.json()}")
    assert response.status_code == 404
