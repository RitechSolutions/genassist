import pytest
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4, UUID

from app.services.feature_flag import FeatureFlagService
from app.repositories.feature_flag import FeatureFlagRepository
from app.schemas.feature_flag import FeatureFlagCreate, FeatureFlagUpdate
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey
from app.db.models.feature_flag import FeatureFlagModel

@pytest.fixture
def mock_repo():
    return AsyncMock(spec=FeatureFlagRepository)

@pytest.fixture
def svc(mock_repo):
    return FeatureFlagService(repo=mock_repo)

@pytest.fixture
def sample_data():
    return {
        "key": "flag_key",
        "val": "on",
        "description": "A test flag",
        "is_active": 1
    }

@pytest.mark.asyncio
async def test_create_success(svc, mock_repo, sample_data):
    dto = FeatureFlagCreate(**sample_data)
    model = create_autospec(FeatureFlagModel, instance=True)
    model.id = uuid4()
    for k, v in sample_data.items():
        setattr(model, k, v)
    mock_repo.create.return_value = model

    result = await svc.create(dto)

    mock_repo.create.assert_called_once_with(dto)
    assert result.key == sample_data["key"]
    assert result.val == sample_data["val"]
    assert result.description == sample_data["description"]
    assert result.is_active == sample_data["is_active"]

@pytest.mark.asyncio
async def test_get_by_id_success(svc, mock_repo, sample_data):
    flag_id = uuid4()
    model = FeatureFlagModel(id=flag_id, **sample_data)
    mock_repo.get_by_id.return_value = model

    result = await svc.get_by_id(flag_id)

    mock_repo.get_by_id.assert_called_once_with(flag_id)
    assert result.id == flag_id
    assert result.key == sample_data["key"]

@pytest.mark.asyncio
async def test_get_by_id_not_found(svc, mock_repo):
    flag_id = uuid4()
    mock_repo.get_by_id.return_value = None

    with pytest.raises(AppException) as exc:
        await svc.get_by_id(flag_id)
    assert exc.value.error_key == ErrorKey.FEATURE_FLAG_NOT_FOUND
    mock_repo.get_by_id.assert_called_once_with(flag_id)

@pytest.mark.asyncio
async def test_get_all(svc, mock_repo, sample_data):
    model1 = FeatureFlagModel(id=uuid4(), **sample_data)
    model2 = FeatureFlagModel(id=uuid4(), **sample_data)
    mock_repo.get_all.return_value = [model1, model2]

    result = await svc.get_all()

    mock_repo.get_all.assert_called_once()
    assert len(result) == 2
    assert result[0].key == sample_data["key"]

@pytest.mark.asyncio
async def test_update_success(svc, mock_repo, sample_data):
    flag_id = uuid4()
    existing_model = FeatureFlagModel(id=flag_id, **sample_data)
    updated_model = FeatureFlagModel(id=flag_id, key="flag_key", val="off", description="Updated", is_active=0)

    mock_repo.get_by_id.return_value = existing_model
    mock_repo.update.return_value = updated_model

    dto = FeatureFlagUpdate(val="off", description="Updated", is_active=0)
    result = await svc.update(flag_id, dto)

    mock_repo.get_by_id.assert_called_once_with(flag_id)
    mock_repo.update.assert_called_once_with(flag_id, dto)
    assert result.val == "off"
    assert result.description == "Updated"
    assert result.is_active == 0

@pytest.mark.asyncio
async def test_update_not_found(svc, mock_repo):
    flag_id = uuid4()
    mock_repo.get_by_id.return_value = None

    dto = FeatureFlagUpdate(val="off")
    with pytest.raises(AppException) as exc:
        await svc.update(flag_id, dto)

    assert exc.value.error_key == ErrorKey.FEATURE_FLAG_NOT_FOUND
    mock_repo.get_by_id.assert_called_once_with(flag_id)

@pytest.mark.asyncio
async def test_delete_success(svc, mock_repo, sample_data):
    flag_id = uuid4()
    model = FeatureFlagModel(id=flag_id, **sample_data)
    mock_repo.get_by_id.return_value = model
    mock_repo.delete.return_value = True

    await svc.delete(flag_id)

    mock_repo.get_by_id.assert_called_once_with(flag_id)
    mock_repo.delete.assert_called_once_with(flag_id)

@pytest.mark.asyncio
async def test_delete_not_found(svc, mock_repo):
    flag_id = uuid4()
    mock_repo.get_by_id.return_value = None

    with pytest.raises(AppException) as exc:
        await svc.delete(flag_id)

    assert exc.value.error_key == ErrorKey.FEATURE_FLAG_NOT_FOUND
    mock_repo.get_by_id.assert_called_once_with(flag_id)
