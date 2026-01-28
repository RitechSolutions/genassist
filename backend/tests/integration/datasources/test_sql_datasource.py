import pytest
from urllib.parse import quote
from app.core.config.settings import settings
from app.schemas.agent_knowledge import KBRead
from app.db.seed.seed_data_config import seed_test_data

import logging

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def new_datasource_data():
    user = quote(settings.DB_USER or "", safe="")
    password = quote(settings.DB_PASS or "", safe="")
    data = {
        "name": "Test SQL Data Source provider",
        "source_type": "Database",
       "connection_data": {
                        "database_type": "postgresql",   
                        "connection_string": f"postgresql://{user}:{password}@{settings.DB_HOST}/{settings.DB_NAME}",
                        "allowed_tables": ['conversations','operators']},
        "is_active": 1,
    }
    return data


@pytest.fixture(scope="module")
def new_kb_data():
    data = {
        "name": "Test Knowledge Base for SQL Sync",
        "description": "A test knowledge base item",
        "type": "database",
        "content": "This is a test knowledge base content",
        "rag_config": {
            "enabled": False,
            "vector_db": {"enabled": False},
            "light_rag": {"enabled": False},
        },
        "llm_provider_id": seed_test_data.llm_provider_id,
    }
    return data

async def create_ds(client, data):
    response = client.post("/api/datasources/", json=data)
    assert response.status_code == 200
    data["id"] = response.json()["id"]  # Store ID for later tests


async def create_kb(client, data):
    response = client.post("/api/genagent/knowledge/items/", json=data)
    assert response.status_code == 200
    kb_data = response.json()
    data["id"] = kb_data["id"]  # Store ID for later tests

@pytest.mark.asyncio(scope="session")
async def test_search_data_source_with_scope(authorized_client, new_datasource_data, new_kb_data):
    
    logger.info(f"Creating datasource: {new_datasource_data}")
    await create_ds(authorized_client, new_datasource_data)
    logger.info(f"Datasource created with ID: {new_datasource_data['id']}")

    logger.info(f"Creating knowledge base: {new_kb_data}")
    new_kb_data["sync_source_id"] = new_datasource_data["id"]
    await create_kb(authorized_client, new_kb_data)
    logger.info(f"Knowledge base created with ID: {new_kb_data['id']}")

    kbid = new_kb_data["id"]

    logger.info(f"Getting knowledge base: {kbid}")
    kb_response = authorized_client.get(f"/api/genagent/knowledge/items/{kbid}")
    assert kb_response.status_code == 200
    kb_data = kb_response.json()
    assert kb_data["sync_source_id"] == new_datasource_data["id"]
    logger.info(f"Knowledge base data: {kb_data}")

    # Use the request scope to properly set up the context


    kbs = [KBRead(**new_kb_data)]
    
    param1 = {
        'query': "How many operators are there in the system?"
    }
    param2 = {
        'query': 'How many conversations have lasted less than 5 minutes?'
    }
    param3 = {
        'query': 'how many conversations have been taken over by operator?'
    }
    results = []
    for param in [param1, param2, param3]:
        logger.info(f"Query: {param['query']}")
        searchParams = {'query': param['query'], 'items': [kb_data]}
        search_response = authorized_client.post("/api/genagent/knowledge/search", json=searchParams)
        assert search_response.status_code == 200
        result = search_response.json()

        # result = await agent_ds_service.search_knowledge(
        #     query=param['query'],
        #     docs_config=kbs,
        # )
        logger.info(f"Results: {result}")
        assert len(result) > 0
        results.append(result)

    # Assert
    assert isinstance(results, list)
    assert len(results) > 0