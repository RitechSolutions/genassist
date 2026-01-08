import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from app.services.agent_knowledge import KnowledgeBaseService
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.agent_knowledge import KBCreate, KBRead
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.knowledge_base import KnowledgeBaseModel


@pytest.fixture
def mock_repository():
    return AsyncMock(spec=KnowledgeBaseRepository)


@pytest.fixture
def knowledge_base_service(mock_repository):
    return KnowledgeBaseService(repository=mock_repository)


@pytest.fixture
def sample_kb_data():
    return {
        "name": "test_kb",
        "description": "Test knowledge base description",
        "type": "file",
        "source": "test_source",
        "content": "Test content",
        "file_path": "/path/to/file",
        "file_type": "text",
        "files": ["/path/to/file.txt"],
        "vector_store": {"config": "test"},
        "rag_config": {
            "enabled": True,
            "vector_db": {"enabled": True},
            "graph_db": {"enabled": False},
            "light_rag": {"enabled": False}
        },
        "extra_metadata": {},
        "embeddings_model": "test-model"
    }


@pytest.mark.asyncio
async def test_get_all_success(knowledge_base_service, mock_repository, sample_kb_data):
    # Setup
    mock_kbs = [
        KnowledgeBaseModel(**{
            **sample_kb_data,
            "id": uuid4()
        })
        for _ in range(3)
    ]
    mock_repository.get_all.return_value = mock_kbs

    # Execute
    result = await knowledge_base_service.get_all()

    # Assert
    mock_repository.get_all.assert_called_once()
    assert len(result) == len(mock_kbs)
    for kb_read in result:
        assert isinstance(kb_read, KBRead)


@pytest.mark.asyncio
async def test_get_by_id_success(knowledge_base_service, mock_repository, sample_kb_data):
    # Setup
    kb_id = uuid4()
    mock_kb = KnowledgeBaseModel(**{
        **sample_kb_data,
        "id": kb_id
    })
    mock_repository.get_by_id.return_value = mock_kb

    # Execute
    result = await knowledge_base_service.get_by_id(kb_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(kb_id)
    assert isinstance(result, KBRead)
    assert result.id == kb_id
    assert result.name == sample_kb_data["name"]


@pytest.mark.asyncio
async def test_get_by_id_not_found(knowledge_base_service, mock_repository):
    # Setup
    kb_id = uuid4()
    mock_repository.get_by_id.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await knowledge_base_service.get_by_id(kb_id)

    assert exc_info.value.error_key == ErrorKey.KB_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(kb_id)


@pytest.mark.asyncio
async def test_get_by_ids_success(knowledge_base_service, mock_repository, sample_kb_data):
    # Setup
    kb_ids = [uuid4() for _ in range(2)]
    mock_kbs = [
        KnowledgeBaseModel(**{
            **sample_kb_data,
            "id": kb_id
        })
        for kb_id in kb_ids
    ]
    mock_repository.get_by_ids.return_value = mock_kbs

    # Execute
    result = await knowledge_base_service.get_by_ids(kb_ids)

    # Assert
    mock_repository.get_by_ids.assert_called_once_with(kb_ids)
    assert len(result) == len(kb_ids)
    for kb_read in result:
        assert isinstance(kb_read, KBRead)


@pytest.mark.asyncio
async def test_create_success(knowledge_base_service, mock_repository, sample_kb_data):
    # Setup
    kb_create = KBCreate(**sample_kb_data)
    mock_kb = KnowledgeBaseModel(**{
        **sample_kb_data,
        "id": uuid4()
    })
    mock_repository.create.return_value = mock_kb

    # Execute
    result = await knowledge_base_service.create(kb_create)

    # Assert
    mock_repository.create.assert_called_once()
    assert isinstance(result, KBRead)
    assert result.name == sample_kb_data["name"]


@pytest.mark.asyncio
async def test_update_success(knowledge_base_service, mock_repository, sample_kb_data):
    # Setup
    kb_id = uuid4()
    update_data = KBCreate(**{
        **sample_kb_data,
        "name": "updated_kb",
        "description": "Updated description"
    })
    mock_kb = KnowledgeBaseModel(**{
        **sample_kb_data,
        "id": kb_id
    })
    mock_repository.get_by_id.return_value = mock_kb
    mock_repository.update.return_value = KnowledgeBaseModel(**{
        **update_data.model_dump(),
        "id": kb_id
    })

    # Execute
    result = await knowledge_base_service.update(kb_id, update_data)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(kb_id)
    mock_repository.update.assert_called_once()
    assert isinstance(result, KBRead)
    assert result.name == update_data.name
    assert result.description == update_data.description


@pytest.mark.asyncio
async def test_update_not_found(knowledge_base_service, mock_repository, sample_kb_data):
    # Setup
    kb_id = uuid4()
    update_data = KBCreate(**sample_kb_data)
    mock_repository.get_by_id.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await knowledge_base_service.update(kb_id, update_data)

    assert exc_info.value.error_key == ErrorKey.KB_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(kb_id)
    mock_repository.update.assert_not_called()


@pytest.mark.asyncio
async def test_delete_success(knowledge_base_service, mock_repository, sample_kb_data):
    # Setup
    kb_id = uuid4()
    mock_kb = KnowledgeBaseModel(**{
        **sample_kb_data,
        "id": kb_id
    })
    mock_repository.get_by_id.return_value = mock_kb

    # Execute
    await knowledge_base_service.delete(kb_id)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(kb_id)
    mock_repository.delete.assert_called_once_with(mock_kb)


@pytest.mark.asyncio
async def test_delete_not_found(knowledge_base_service, mock_repository):
    # Setup
    kb_id = uuid4()
    mock_repository.get_by_id.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await knowledge_base_service.delete(kb_id)

    assert exc_info.value.error_key == ErrorKey.KB_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(kb_id)
    mock_repository.delete.assert_not_called()
