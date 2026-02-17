import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

from app.services.llm_providers import LlmProviderService
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.llm import LlmProviderCreate, LlmProviderUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm import LlmProvidersModel


@pytest.fixture(autouse=True)
def init_cache():
    """Initialize FastAPICache with in-memory backend for unit tests."""
    FastAPICache.init(InMemoryBackend())
    yield
    FastAPICache.reset()


@pytest.fixture
def mock_repository():
    return AsyncMock(spec=LlmProviderRepository)


@pytest.fixture
def llm_provider_service(mock_repository):
    return LlmProviderService(repository=mock_repository)


@pytest.fixture
def sample_llm_provider_data():
    return {
        "name": "test_provider",
        "llm_model_provider": "openai",
        "connection_data": {
            "api_key": "sk-test-key-for-unit-tests"
        },
        "is_active": 1,
        "llm_model": "gpt-3.5-turbo"
    }


@pytest.mark.asyncio
async def test_create_success(llm_provider_service, mock_repository, sample_llm_provider_data):
    provider_create = LlmProviderCreate(**sample_llm_provider_data)
    mock_provider = LlmProvidersModel(
        id=uuid4(),
        **sample_llm_provider_data
    )
    mock_repository.create.return_value = mock_provider

    result = await llm_provider_service.create(provider_create)

    mock_repository.create.assert_called_once_with(provider_create)
    assert result.name == sample_llm_provider_data["name"]
    assert result.llm_model_provider == sample_llm_provider_data["llm_model_provider"]
    assert result.connection_data == sample_llm_provider_data["connection_data"]
    assert result.llm_model == sample_llm_provider_data["llm_model"]


@pytest.mark.asyncio
async def test_get_by_id_success(llm_provider_service, mock_repository, sample_llm_provider_data):
    provider_id = uuid4()
    mock_provider = LlmProvidersModel(
        id=provider_id,
        **sample_llm_provider_data
    )
    mock_repository.get_by_id.return_value = mock_provider

    result = await llm_provider_service.get_by_id(provider_id)

    mock_repository.get_by_id.assert_called_once_with(provider_id)
    assert result.id == provider_id
    assert result.name == sample_llm_provider_data["name"]
    assert result.llm_model_provider == sample_llm_provider_data["llm_model_provider"]


@pytest.mark.asyncio
async def test_get_by_id_not_found(llm_provider_service, mock_repository):
    provider_id = uuid4()
    mock_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as exc_info:
        await llm_provider_service.get_by_id(provider_id)

    assert exc_info.value.error_key == ErrorKey.LLM_PROVIDER_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(provider_id)


@pytest.mark.asyncio
async def test_get_all_success(llm_provider_service, mock_repository, sample_llm_provider_data):
    mock_providers = [
        LlmProvidersModel(
            id=uuid4(),
            **{**sample_llm_provider_data, "name": f"provider{i}"}
        )
        for i in range(3)
    ]
    mock_repository.get_all.return_value = mock_providers

    result = await llm_provider_service.get_all()

    mock_repository.get_all.assert_called_once()
    assert len(result) == len(mock_providers)
    for i, provider in enumerate(result):
        assert provider.name == f"provider{i}"
        assert provider.llm_model_provider == sample_llm_provider_data["llm_model_provider"]


@pytest.mark.asyncio
async def test_update_success(llm_provider_service, mock_repository, sample_llm_provider_data):
    provider_id = uuid4()
    update_data = LlmProviderUpdate(
        name="updated_provider",
        llm_model_provider="anthropic",
        llm_model="claude-2"
    )
    mock_provider = LlmProvidersModel(
        id=provider_id,
        **sample_llm_provider_data
    )
    mock_repository.get_by_id.return_value = mock_provider

    updated_provider = LlmProvidersModel(
        id=provider_id,
        **{**sample_llm_provider_data, **update_data.model_dump(exclude_unset=True)}
    )
    mock_repository.update.return_value = updated_provider

    result = await llm_provider_service.update(provider_id, update_data)

    mock_repository.get_by_id.assert_called_once_with(provider_id)
    mock_repository.update.assert_called_once()
    assert result.id == provider_id
    assert result.name == update_data.name
    assert result.llm_model_provider == update_data.llm_model_provider
    assert result.llm_model == update_data.llm_model


@pytest.mark.asyncio
async def test_delete_success(llm_provider_service, mock_repository, sample_llm_provider_data):
    provider_id = uuid4()
    mock_provider = LlmProvidersModel(
        id=provider_id,
        **sample_llm_provider_data
    )
    mock_repository.get_by_id.return_value = mock_provider

    result = await llm_provider_service.delete(provider_id)

    mock_repository.get_by_id.assert_called_once_with(provider_id)
    mock_repository.delete.assert_called_once_with(mock_provider)
    assert result["message"] == f"Deleted LLM Provider with ID {provider_id}"
