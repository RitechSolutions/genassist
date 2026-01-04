import pytest
import logging

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_list_operators(client):
    response = client.get("/api/operators/", headers={"X-API-Key": "test123"})
    logger.info("operators: %s", response.json())
    assert response.status_code == 200
