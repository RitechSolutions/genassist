import pytest
from uuid import UUID
from httpx import AsyncClient
from fastapi import FastAPI
<<<<<<< HEAD:tests/datasources/test_datasources.py
=======
import logging

logger = logging.getLogger(__name__)
>>>>>>> development:tests/integration/datasources/test_datasources.py

@pytest.mark.asyncio
async def test_create_datasource(client):
    # Test data
    datasource_data = {
        "name": "Test Datasource",
        "source_type": "postgresql",
        "connection_data": {
            "url": "postgresql://user:pass@localhost:5432/db"
        },
        "is_active": 1
    }
    
    # Create datasource
    response = client.post(
        "/api/datasources/",
        headers={"X-API-Key": "test123"},
        json=datasource_data
    )
    assert response.status_code == 200
    created_datasource = response.json()
    logger.info(f" test create datasource response:{created_datasource}")

    assert created_datasource["name"] == datasource_data["name"]
    assert created_datasource["source_type"] == datasource_data["source_type"]
    assert created_datasource["connection_data"] == datasource_data["connection_data"]
    assert created_datasource["is_active"] == datasource_data["is_active"]
    
    return created_datasource

@pytest.mark.asyncio
async def test_get_datasource_by_id(client):
    # First create a datasource
    datasource = await test_create_datasource(client)
    datasource_id = datasource["id"]
    
    # Get the datasource by ID
    response = client.get(
        f"/api/datasources/{datasource_id}",
        headers={"X-API-Key": "test123"}
    )
    assert response.status_code == 200
    retrieved_datasource = response.json()
    assert retrieved_datasource["id"] == datasource_id
    assert retrieved_datasource["name"] == datasource["name"]

@pytest.mark.asyncio
async def test_get_all_datasources(client):
    # First create a datasource
    await test_create_datasource(client)
    
    # Get all datasources
    response = client.get(
        "/api/datasources",
        headers={"X-API-Key": "test123"}
    )
    assert response.status_code == 200
    datasources = response.json()
    assert isinstance(datasources, list)
    assert len(datasources) > 0

@pytest.mark.asyncio
async def test_update_datasource(client):
    # First create a datasource
    datasource = await test_create_datasource(client)
    datasource_id = datasource["id"]
    
    # Update data
    update_data = {
        "name": "Updated Datasource",
        "is_active": 0
    }
    
    # Update the datasource
    response = client.put(
        f"/api/datasources/{datasource_id}",
        headers={"X-API-Key": "test123"},
        json=update_data
    )
    assert response.status_code == 200
    updated_datasource = response.json()
    assert updated_datasource["id"] == datasource_id
    assert updated_datasource["name"] == update_data["name"]
    assert updated_datasource["is_active"] == update_data["is_active"]
    # Check that other fields remain unchanged
    assert updated_datasource["source_type"] == datasource["source_type"]
    assert updated_datasource["connection_data"] == datasource["connection_data"]

@pytest.mark.asyncio
async def test_delete_datasource(client):
    # First create a datasource
    datasource = await test_create_datasource(client)
    datasource_id = datasource["id"]
    
    # Delete the datasource
    response = client.delete(
        f"/api/datasources/{datasource_id}",
        headers={"X-API-Key": "test123"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Datasource deleted successfully"
    
    # Verify the datasource is deleted
    response = client.get(
        f"/api/datasources/{datasource_id}",
        headers={"X-API-Key": "test123"}
    )
    assert response.status_code == 400#TODO: should this be 404?

@pytest.mark.asyncio
async def test_unauthorized_access(client):
    # Test unauthorized access to all endpoints
    endpoints = [
        ("POST", "/api/datasources"),
        ("GET", "/api/datasources"),
        ("GET", "/api/datasources/123e4567-e89b-12d3-a456-426614174000"),
        ("PUT", "/api/datasources/123e4567-e89b-12d3-a456-426614174000"),
        ("DELETE", "/api/datasources/123e4567-e89b-12d3-a456-426614174000")
    ]
    
    for method, endpoint in endpoints:
        if method == "POST":
            response = client.post(endpoint, json={}, headers={"Authorization": "",  "X-API-Key": ""})
        elif method == "GET":
            response = client.get(endpoint, headers={"Authorization": "",  "X-API-Key": ""})
        elif method == "PUT":
            response = client.put(endpoint, json={}, headers={"Authorization": "",  "X-API-Key": ""})
        elif method == "DELETE":
            response = client.delete(endpoint, headers={"Authorization": "",  "X-API-Key": ""})
        
        assert response.status_code == 401 