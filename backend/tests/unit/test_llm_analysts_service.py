import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4
from app.services.llm_analysts import LlmAnalystService
from app.repositories.llm_analysts import LlmAnalystRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.llm import LlmAnalystCreate, LlmAnalystUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm import LlmAnalystModel

@pytest.fixture
def mock_repository():
    return AsyncMock(spec=LlmAnalystRepository)

@pytest.fixture
def mock_llm_provider_repository():
    return AsyncMock(spec=LlmProviderRepository)

@pytest.fixture
def llm_analyst_service(mock_repository, mock_llm_provider_repository):
    return LlmAnalystService(repository=mock_repository, llm_provider_repository=mock_llm_provider_repository)

@pytest.fixture
def sample_llm_analyst_data():
    return {
        "name": "test_analyst",
        "llm_provider_id": uuid4(),
        "prompt": "Test prompt",
        "is_active": 1
    }

@pytest.mark.asyncio
async def test_create_success(llm_analyst_service, mock_repository, mock_llm_provider_repository, sample_llm_analyst_data):
    # Setup
    analyst_create = LlmAnalystCreate(**sample_llm_analyst_data)
    mock_llm_provider_repository.get_by_id.return_value = MagicMock(id=sample_llm_analyst_data["llm_provider_id"])
    mock_analyst = LlmAnalystModel(**sample_llm_analyst_data)
    mock_repository.create.return_value = mock_analyst
    mock_repository.get_by_id.return_value = mock_analyst

    # Execute
    result = await llm_analyst_service.create(analyst_create)

    # Assert
    mock_llm_provider_repository.get_by_id.assert_called_once_with(analyst_create.llm_provider_id)
    mock_repository.create.assert_called_once_with(analyst_create)
    assert result.name == sample_llm_analyst_data["name"]
    assert result.llm_provider_id == sample_llm_analyst_data["llm_provider_id"]
    assert result.prompt == sample_llm_analyst_data["prompt"]

@pytest.mark.asyncio
async def test_get_by_id_success(llm_analyst_service, mock_repository, sample_llm_analyst_data):
    # Setup
    analyst_id = uuid4()
    mock_analyst = LlmAnalystModel(id=analyst_id, **sample_llm_analyst_data)
    mock_repository.get_by_id.return_value = mock_analyst

    # Execute
    result = await llm_analyst_service.get_by_id(analyst_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(analyst_id)
    assert result.id == analyst_id
    assert result.name == sample_llm_analyst_data["name"]

@pytest.mark.asyncio
async def test_get_by_id_not_found(llm_analyst_service, mock_repository):
    # Setup
    analyst_id = uuid4()
    mock_repository.get_by_id.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await llm_analyst_service.get_by_id(analyst_id)
    
    assert exc_info.value.error_key == ErrorKey.LLM_ANALYST_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(analyst_id)

@pytest.mark.asyncio
async def test_get_all_success(llm_analyst_service, mock_repository, sample_llm_analyst_data):
    # Setup
    mock_analysts = [
        LlmAnalystModel(id=uuid4(), **sample_llm_analyst_data)
        for _ in range(2)
    ]
    mock_repository.get_all.return_value = mock_analysts

    # Execute
    result = await llm_analyst_service.get_all()

    # Assert
    mock_repository.get_all.assert_called_once()
    assert result == mock_analysts

@pytest.mark.asyncio
async def test_update_success(llm_analyst_service, mock_repository, sample_llm_analyst_data):
    # Setup
    analyst_id = uuid4()
    update_data = LlmAnalystUpdate(
        name="updated_analyst",
        prompt="Updated prompt"
    )
    mock_analyst = LlmAnalystModel(id=analyst_id, **sample_llm_analyst_data)
    mock_repository.get_by_id.return_value = mock_analyst

    updated_data = {
        **sample_llm_analyst_data,
        **update_data.model_dump(exclude_unset=True),
        "id": analyst_id
    }
    updated_analyst = LlmAnalystModel(**updated_data)
    mock_repository.update.return_value = updated_analyst

    # Execute
    result = await llm_analyst_service.update(analyst_id, update_data)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(analyst_id)
    mock_repository.update.assert_called_once()
    assert result.id == analyst_id
    assert result.name == update_data.name
    assert result.prompt == update_data.prompt

@pytest.mark.asyncio
async def test_delete_success(llm_analyst_service, mock_repository, sample_llm_analyst_data):
    # Setup
    analyst_id = uuid4()
    mock_analyst = LlmAnalystModel(id=analyst_id, **sample_llm_analyst_data)
    mock_repository.get_by_id.return_value = mock_analyst

    # Execute
    result = await llm_analyst_service.delete(analyst_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(analyst_id)
    mock_repository.delete.assert_called_once_with(mock_analyst)
    assert result["message"] == f"LlmAnalyst with ID {analyst_id} has been deleted." 