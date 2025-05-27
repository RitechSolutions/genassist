import pytest
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4, UUID
from app.services.app_settings import AppSettingsService
from app.repositories.app_settings import AppSettingsRepository
from app.schemas.app_settings import AppSettingsCreate, AppSettingsUpdate
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.error_messages import ErrorKey
from app.db.models.app_settings import AppSettingsModel


@pytest.fixture
def mock_repository():
    return AsyncMock(spec=AppSettingsRepository)

@pytest.fixture
def app_settings_service(mock_repository):
    return AppSettingsService(mock_repository)

@pytest.fixture
def sample_app_setting_data():
    return {
        "key": "app_setting_key",
        "value": "app_setting_value",
        "description": "description of the app settings",
        "is_active": 1,
        "encrypted": 0
    }

@pytest.mark.asyncio
async def test_create_app_setting(app_settings_service, mock_repository, sample_app_setting_data):
    app_setting_create = AppSettingsCreate(**sample_app_setting_data)
    mock_model = create_autospec(AppSettingsModel, instance=True)
    mock_model.id = uuid4()
    for key, val in sample_app_setting_data.items():
        setattr(mock_model, key, val)
    
    mock_repository.create.return_value = mock_model

    result = await app_settings_service.create(app_setting_create)

    mock_repository.create.assert_called_once_with(app_setting_create)
    assert result.key == sample_app_setting_data["key"]
    assert result.value == sample_app_setting_data["value"]

@pytest.mark.asyncio
async def test_get_app_setting_by_id_success(app_settings_service, mock_repository, sample_app_setting_data):
    setting_id = uuid4()
    mock_model = create_autospec(AppSettingsModel, instance=True)
    mock_model.id = setting_id
    for key, val in sample_app_setting_data.items():
        setattr(mock_model, key, val)
    
    mock_repository.get_by_id.return_value = mock_model

    result = await app_settings_service.get_by_id(setting_id)

    mock_repository.get_by_id.assert_called_once_with(setting_id)
    assert result.id == setting_id

@pytest.mark.asyncio
async def test_get_app_setting_by_id_not_found(app_settings_service, mock_repository):
    setting_id = uuid4()
    mock_repository.get_by_id.side_effect = AppException(error_key=ErrorKey.APP_SETTINGS_NOT_FOUND)

    with pytest.raises(AppException) as exc_info:
        await app_settings_service.get_by_id(setting_id)

    assert exc_info.value.error_key == ErrorKey.APP_SETTINGS_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(setting_id)

@pytest.mark.asyncio
async def test_update_app_setting_success(app_settings_service, mock_repository, sample_app_setting_data):
    setting_id = uuid4()
    update_data = AppSettingsUpdate(value="updated", is_active=0)

    mock_updated = create_autospec(AppSettingsModel, instance=True)
    mock_updated.id = setting_id
    mock_updated.value = update_data.value
    mock_updated.is_active = update_data.is_active
    # Add all required fields for AppSettingsRead
    mock_updated.key = sample_app_setting_data["key"]
    mock_updated.description = sample_app_setting_data["description"]
    mock_updated.encrypted = sample_app_setting_data["encrypted"]

    mock_repository.update.return_value = mock_updated

    result = await app_settings_service.update(setting_id, update_data)

    mock_repository.update.assert_called_once_with(setting_id, update_data)
    assert result.value == "updated"
    
@pytest.mark.asyncio
async def test_delete_app_setting(app_settings_service, mock_repository):
    setting_id = uuid4()

    await app_settings_service.delete(setting_id)

    mock_repository.delete.assert_called_once_with(setting_id)
