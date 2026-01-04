import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4
from app.services.agent_tool import ToolService
from app.repositories.tool import ToolRepository
from app.schemas.agent_tool import ToolConfigBase, ToolConfigRead
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.tool import ToolModel

@pytest.fixture
def mock_repository():
    return AsyncMock(spec=ToolRepository)

@pytest.fixture
def tool_service(mock_repository):
    return ToolService(repository=mock_repository)

@pytest.fixture
def sample_tool_data():
    return {
        "name": "test_tool",
        "description": "Test tool description",
        "type": "api",
        "api_config": {
            "endpoint": "https://api.test.com",
            "method": "GET",
            "headers": {},
            "query_params": {},
            "body": {}
        },
        "parameters_schema": {}
    }

@pytest.mark.asyncio
async def test_create_success(tool_service, mock_repository, sample_tool_data):
    # Setup
    tool_create = ToolConfigBase(**sample_tool_data)
    mock_tool = ToolModel(id=uuid4(), **sample_tool_data)
    mock_repository.create.return_value = mock_tool

    # Execute
    result = await tool_service.create(tool_create)

    # Assert
    mock_repository.create.assert_called_once()
    assert isinstance(result, ToolConfigRead)
    assert result.name == sample_tool_data["name"]
    assert result.description == sample_tool_data["description"]
    assert result.type == sample_tool_data["type"]

@pytest.mark.asyncio
async def test_get_by_id_success(tool_service, mock_repository, sample_tool_data):
    # Setup
    tool_id = uuid4()
    mock_tool = ToolModel(id=tool_id, **sample_tool_data)
    mock_repository.get_by_id.return_value = mock_tool

    # Execute
    result = await tool_service.get_by_id(tool_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(tool_id)
    assert isinstance(result, ToolConfigRead)
    assert result.id == tool_id
    assert result.name == sample_tool_data["name"]
    assert result.description == sample_tool_data["description"]

@pytest.mark.asyncio
async def test_get_by_id_not_found(tool_service, mock_repository):
    # Setup
    tool_id = uuid4()
    mock_repository.get_by_id.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await tool_service.get_by_id(tool_id)
    
    assert exc_info.value.error_key == ErrorKey.TOOL_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(tool_id)

@pytest.mark.asyncio
async def test_get_all_success(tool_service, mock_repository, sample_tool_data):
    # Setup
    mock_tools = [
        ToolModel(
            id=uuid4(),
            **{
                **sample_tool_data,
                "name": f"tool{i}"
            }
        )
        for i in range(3)
    ]
    mock_repository.get_all.return_value = mock_tools

    # Execute
    result = await tool_service.get_all()

    # Assert
    mock_repository.get_all.assert_called_once()
    assert len(result) == len(mock_tools)
    assert all(isinstance(tool, ToolConfigRead) for tool in result)
    for i, tool in enumerate(result):
        assert tool.name == f"tool{i}"
        assert tool.type == sample_tool_data["type"]

@pytest.mark.asyncio
async def test_update_success(tool_service, mock_repository, sample_tool_data):
    # Setup
    tool_id = uuid4()
    update_data = ToolConfigBase(
        name="updated_tool",
        description="Updated description",
        type="function",
        parameters_schema={"param1": {"type": "string"}}
    )
    mock_tool = ToolModel(id=tool_id, **sample_tool_data)
    mock_repository.get_by_id.return_value = mock_tool
    
    updated_tool = ToolModel(
        id=tool_id,
        **{
            **sample_tool_data,
            **update_data.model_dump(exclude_unset=True)
        }
    )
    mock_repository.update.return_value = updated_tool

    # Execute
    result = await tool_service.update(tool_id, update_data)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(tool_id)
    mock_repository.update.assert_called_once()
    assert isinstance(result, ToolConfigRead)
    assert result.id == tool_id
    assert result.name == update_data.name
    assert result.description == update_data.description
    assert result.type == update_data.type

@pytest.mark.asyncio
async def test_delete_success(tool_service, mock_repository, sample_tool_data):
    # Setup
    tool_id = uuid4()
    mock_tool = ToolModel(id=tool_id, **sample_tool_data)
    mock_repository.get_by_id.return_value = mock_tool

    # Execute
    await tool_service.delete(tool_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(tool_id)
    mock_repository.delete.assert_called_once_with(mock_tool) 