import pytest
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4
from datetime import datetime
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
        "name": "Test App Setting",
        "type": "Other",
        "values": {
            "test_key": "test_value",
            "another_key": "another_value"
        },
        "description": "description of the app settings",
        "is_active": 1
    }

@pytest.mark.asyncio
async def test_create_app_setting(app_settings_service, mock_repository, sample_app_setting_data):
    app_setting_create = AppSettingsCreate(**sample_app_setting_data)
    mock_model = create_autospec(AppSettingsModel, instance=True)
    mock_model.id = uuid4()
    for key, val in sample_app_setting_data.items():
        setattr(mock_model, key, val)
    mock_model.created_at = datetime.now()
    mock_model.updated_at = datetime.now()

    # Mock: no existing setting with same name and type
    mock_repository.get_by_type_and_name.return_value = None
    # Mock: create returns the new model
    mock_repository.create.return_value = mock_model

    result = await app_settings_service.create(app_setting_create)

    # The service checks for duplicates and validates/encrypts values
    mock_repository.get_by_type_and_name.assert_called_once_with(
        sample_app_setting_data["type"],
        sample_app_setting_data["name"]
    )
    mock_repository.create.assert_called_once()
    assert result.name == sample_app_setting_data["name"]
    assert result.type == sample_app_setting_data["type"]
    assert result.values == sample_app_setting_data["values"]

@pytest.mark.asyncio
async def test_get_app_setting_by_id_success(app_settings_service, mock_repository, sample_app_setting_data):
    setting_id = uuid4()
    mock_model = create_autospec(AppSettingsModel, instance=True)
    mock_model.id = setting_id
    for key, val in sample_app_setting_data.items():
        setattr(mock_model, key, val)
    mock_model.created_at = datetime.now()
    mock_model.updated_at = datetime.now()

    mock_repository.get_by_id.return_value = mock_model

    result = await app_settings_service.get_by_id(setting_id)

    mock_repository.get_by_id.assert_called_once_with(setting_id)
    assert result.id == setting_id
    assert result.name == sample_app_setting_data["name"]
    assert result.type == sample_app_setting_data["type"]
    assert result.values == sample_app_setting_data["values"]

@pytest.mark.asyncio
async def test_get_app_setting_by_id_not_found(app_settings_service, mock_repository):
    setting_id = uuid4()
    mock_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as exc_info:
        await app_settings_service.get_by_id(setting_id)

    assert exc_info.value.error_key == ErrorKey.APP_SETTINGS_NOT_FOUND
    mock_repository.get_by_id.assert_called_once_with(setting_id)

@pytest.mark.asyncio
async def test_update_app_setting_success(app_settings_service, mock_repository, sample_app_setting_data):
    setting_id = uuid4()
    update_data = AppSettingsUpdate(
        values={"test_key": "updated_value", "another_key": "another_value"},
        is_active=0
    )

    # Mock existing setting
    mock_existing = create_autospec(AppSettingsModel, instance=True)
    mock_existing.id = setting_id
    mock_existing.type = sample_app_setting_data["type"]
    for key, val in sample_app_setting_data.items():
        setattr(mock_existing, key, val)

    # Mock updated setting
    mock_updated = create_autospec(AppSettingsModel, instance=True)
    mock_updated.id = setting_id
    mock_updated.name = sample_app_setting_data["name"]
    mock_updated.type = sample_app_setting_data["type"]
    mock_updated.values = update_data.values
    mock_updated.is_active = update_data.is_active
    mock_updated.description = sample_app_setting_data["description"]
    mock_updated.created_at = datetime.now()
    mock_updated.updated_at = datetime.now()

    mock_repository.get_by_id.return_value = mock_existing
    mock_repository.update.return_value = mock_updated

    result = await app_settings_service.update(setting_id, update_data)

    mock_repository.update.assert_called_once()
    assert result.values == update_data.values
    assert result.is_active == update_data.is_active

@pytest.mark.asyncio
async def test_delete_app_setting(app_settings_service, mock_repository):
    setting_id = uuid4()

    await app_settings_service.delete(setting_id)

    mock_repository.delete.assert_called_once_with(setting_id)
