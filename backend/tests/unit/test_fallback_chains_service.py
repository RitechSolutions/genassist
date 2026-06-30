"""Unit tests for FallbackChainService — focused on provider-id validation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.fallback_chains import FallbackChainRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.fallback_chain import FallbackChainCreate
from app.services.fallback_chains import FallbackChainService


@pytest.fixture(autouse=True)
def init_cache():
    FastAPICache.init(InMemoryBackend())
    yield
    FastAPICache.reset()


@pytest.fixture
def mock_repository():
    return AsyncMock(spec=FallbackChainRepository)


@pytest.fixture
def mock_llm_repository():
    return AsyncMock(spec=LlmProviderRepository)


@pytest.fixture
def service(mock_repository, mock_llm_repository):
    return FallbackChainService(
        repository=mock_repository, llm_provider_repository=mock_llm_repository
    )


@pytest.mark.asyncio
async def test_create_success_when_all_providers_resolve(service, mock_repository, mock_llm_repository):
    pid = str(uuid4())
    mock_llm_repository.get_by_id.return_value = object()  # provider exists
    created = SimpleNamespace(id=uuid4(), name="chain", provider_ids=[pid])
    mock_repository.create.return_value = created

    data = FallbackChainCreate(name="chain", provider_ids=[pid], retry_policy={"retry_count": 1, "backoff_seconds": 1})
    result = await service.create(data)

    assert result.name == "chain"
    mock_repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_rejects_dangling_provider(service, mock_repository, mock_llm_repository):
    mock_llm_repository.get_by_id.return_value = None  # provider does not exist

    data = FallbackChainCreate(name="chain", provider_ids=[str(uuid4())])
    with pytest.raises(AppException) as exc:
        await service.create(data)

    assert exc.value.error_key == ErrorKey.FALLBACK_CHAIN_INVALID_PROVIDER
    mock_repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_get_by_id_not_found_raises(service, mock_repository):
    mock_repository.get_by_id.return_value = None
    with pytest.raises(AppException) as exc:
        await service.get_by_id(uuid4())
    assert exc.value.error_key == ErrorKey.FALLBACK_CHAIN_NOT_FOUND
