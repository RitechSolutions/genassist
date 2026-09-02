import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4
from datetime import datetime
import os

from app.schemas.filter import BaseFilterModel
from app.services.users import UserService
from app.repositories.user_types import UserTypesRepository
from app.repositories.users import UserRepository
from app.schemas.role import RoleRead
from app.schemas.user import UserCreate, UserRead, UserTypeRead, UserUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

# Test-only credentials - these are intentionally simple for unit testing
# and are never used in production. They can be overridden via environment variables.
TEST_USERNAME = os.environ.get('TEST_USER_USERNAME', 'testuser')
TEST_EMAIL = os.environ.get('TEST_USER_EMAIL', 'test@example.com')
TEST_PASSWORD = os.environ.get('TEST_USER_PASSWORD', 'testpassword')  # nosec B105 - test credential
# Test fixture for non-existent user scenarios - not a real credential
TEST_NONEXISTENT_USERNAME = os.environ.get('TEST_NONEXISTENT_USERNAME', 'nonexistent_user_test')

@pytest.fixture
def mock_repository():
    return AsyncMock(spec=UserRepository)

@pytest.fixture
def mock_user_types_repository():
    return AsyncMock(spec=UserTypesRepository)

@pytest.fixture
def user_service(mock_repository, mock_user_types_repository):
    return UserService(
        repository=mock_repository,
        user_types_repository=mock_user_types_repository,
    )

@pytest.fixture
def sample_user_data():
    return {
        "username": TEST_USERNAME,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "is_active": 1,
        "user_type_id": uuid4(),
        "role_ids": [uuid4()]
    }

@pytest.mark.asyncio
async def test_create_user_success(user_service, mock_repository, sample_user_data):
    # Setup
    user_create = UserCreate(**sample_user_data)
    mock_repository.get_by_username.return_value = None
    mock_repository.get_by_email.return_value = None
    mock_repository.create.return_value = MagicMock(id=uuid4())
    mock_repository.get_full.return_value = MagicMock(
        id=uuid4(),
        username=sample_user_data["username"],
        email=sample_user_data["email"],
        is_active=sample_user_data["is_active"]
    )

    # Execute
    result = await user_service.create(user_create)

    # Assert
    mock_repository.get_by_username.assert_called_once_with(user_create.username)
    mock_repository.get_by_email.assert_called_once_with(
        user_create.email, include_deleted=True
    )
    mock_repository.create.assert_called_once()
    mock_repository.get_full.assert_called_once()
    assert result.username == sample_user_data["username"]
    assert result.email == sample_user_data["email"]

@pytest.mark.asyncio
async def test_create_user_duplicate_username(user_service, mock_repository, sample_user_data):
    # Setup
    user_create = UserCreate(**sample_user_data)
    mock_repository.get_by_username.return_value = MagicMock()

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await user_service.create(user_create)
    
    assert exc_info.value.error_key == ErrorKey.USERNAME_ALREADY_EXISTS
    mock_repository.get_by_username.assert_called_once_with(user_create.username)
    mock_repository.get_by_email.assert_not_called()
    mock_repository.create.assert_not_called()

@pytest.mark.asyncio
async def test_create_user_duplicate_email(user_service, mock_repository, sample_user_data):
    user_create = UserCreate(**sample_user_data)
    mock_repository.get_by_username.return_value = None
    mock_repository.get_by_email.return_value = MagicMock()

    with pytest.raises(AppException) as exc_info:
        await user_service.create(user_create)

    assert exc_info.value.error_key == ErrorKey.EMAIL_ALREADY_EXISTS
    mock_repository.get_by_username.assert_called_once_with(user_create.username)
    mock_repository.get_by_email.assert_called_once_with(
        user_create.email, include_deleted=True
    )
    mock_repository.create.assert_not_called()

@pytest.mark.asyncio
async def test_create_user_duplicate_entra_oid(user_service, mock_repository, sample_user_data):
    oid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    sample_user_data["entra_oid"] = oid
    user_create = UserCreate(**sample_user_data)
    mock_repository.get_by_username.return_value = None
    mock_repository.get_by_email.return_value = None
    mock_repository.get_by_entra_oid.return_value = MagicMock()

    with pytest.raises(AppException) as exc_info:
        await user_service.create(user_create)

    assert exc_info.value.error_key == ErrorKey.ENTRA_OID_IN_USE
    mock_repository.get_by_entra_oid.assert_called_once_with(oid)
    mock_repository.create.assert_not_called()

@pytest.mark.asyncio
async def test_get_user_by_id_success(user_service, mock_repository):
    # Setup
    user_id = uuid4()
    mock_user = UserRead(
            id=user_id,
            username="testuser",
            email="test@example.com",
            is_active=1,
            roles=[],
            user_type=UserTypeRead(id=UUID("00000196-edb1-2b80-a681-167fc2a697dd"), name="interactive", created_at=datetime.now(), updated_at=datetime.now()),
            api_keys=[]
            )
    mock_repository.get_full.return_value = mock_user

    # Execute
    result = await user_service.get_by_id(user_id)

    # Assert
    mock_repository.get_full.assert_called_once_with(user_id)
    assert result == mock_user

@pytest.mark.asyncio
async def test_get_user_by_id_not_found(user_service, mock_repository):
    # Setup
    user_id = uuid4()
    mock_repository.get_full.return_value = None

    # Execute
    result = await user_service.get_by_id(user_id)

    # Assert
    mock_repository.get_full.assert_called_once_with(user_id)
    assert result is None

@pytest.mark.asyncio
async def test_get_user_by_username_success(user_service, mock_repository):
    # Setup
    username = TEST_USERNAME
    mock_user = MagicMock(
        id=uuid4(),
        username=username,
        email=TEST_EMAIL,
        is_active=1,
        user_type = UserTypeRead(id=UUID('00000196-edb1-2b80-a681-167fc2a697dd'), name="interactive", created_at=datetime.now(), updated_at=datetime.now())
    )
    mock_repository.get_by_username.return_value = mock_user

    # Execute
    result = await user_service.get_by_username(username)

    # Assert
    mock_repository.get_by_username.assert_called_once_with(username, include_deleted=False)
    assert result == mock_user

@pytest.mark.asyncio
async def test_get_user_by_username_not_found(user_service, mock_repository):
    # Setup - using a clearly non-existent username for negative test
    username = TEST_NONEXISTENT_USERNAME
    mock_repository.get_by_username.return_value = None

    # Execute and Assert
    with pytest.raises(AppException) as exc_info:
        await user_service.get_by_username(username)

    assert exc_info.value.error_key == ErrorKey.USER_NOT_FOUND
    mock_repository.get_by_username.assert_called_once_with(username, include_deleted=False)

@pytest.mark.asyncio
async def test_get_user_by_username_not_found_no_throw(user_service, mock_repository):
    # Setup - using a clearly non-existent username for negative test
    username = TEST_NONEXISTENT_USERNAME
    mock_repository.get_by_username.return_value = None

    # Execute
    result = await user_service.get_by_username(username, throw_not_found=False)

    # Assert
    mock_repository.get_by_username.assert_called_once_with(username, include_deleted=False)
    assert result is None

@pytest.mark.asyncio
async def test_update_user_success(user_service, mock_repository, mock_user_types_repository):
    # Setup
    user_id = uuid4()
    update_data = UserUpdate(
        email="updated@example.com",
        is_active=0,
        user_type_id=UUID('00000196-edb1-2b80-a681-167fc2a697dd'),
    )
    mock_updated_user = UserRead(
            id=user_id,
            username="testuser",
            email="updated@example.com",
            is_active=0,
            roles=[RoleRead(id=uuid4(), name="admin", created_at=datetime.now(), updated_at=datetime.now())],
            user_type=UserTypeRead(id=UUID("00000196-edb1-2b80-a681-167fc2a697dd"), name="interactive", created_at=datetime.now(), updated_at=datetime.now()),
            api_keys=[]
            )
    mock_repository.get_by_email.return_value = None
    mock_repository.update.return_value = mock_updated_user
    mock_repository.get_full.return_value = mock_updated_user
    mock_user_types_repository.get_by_id.return_value = mock_updated_user.user_type

    # Execute
    result = await user_service.update(user_id, update_data)

    # Assert
    mock_repository.get_by_email.assert_called_once_with(
        update_data.email, include_deleted=True
    )
    mock_repository.update.assert_called_once_with(user_id, update_data)
    mock_repository.get_full.assert_called_with(mock_updated_user.id)
    mock_user_types_repository.get_by_id.assert_called_once_with(update_data.user_type_id)
    assert result == mock_updated_user

CONSOLE_TYPE_ID = UUID("00000196-edb1-2b80-a681-167fc2a697de")
INTERACTIVE_TYPE_ID = UUID("00000196-edb1-2b80-a681-167fc2a697dd")

def _user_type(type_id: UUID, name: str) -> UserTypeRead:
    return UserTypeRead(id=type_id, name=name, created_at=datetime.now(), updated_at=datetime.now())

def _user(user_id: UUID, user_type: UserTypeRead, group_id: UUID | None = None) -> UserRead:
    return UserRead(
        id=user_id,
        username="testuser",
        email="test@example.com",
        is_active=1,
        roles=[],
        user_type=user_type,
        api_keys=[],
        group_id=group_id,
    )

def test_user_update_allows_empty_role_ids():
    assert UserUpdate(role_ids=[]).role_ids == []
    assert UserUpdate().role_ids is None

def test_user_create_still_rejects_empty_role_ids(sample_user_data):
    with pytest.raises(ValidationError):
        UserCreate(**{**sample_user_data, "role_ids": []})

@pytest.mark.asyncio
async def test_update_console_user_empty_role_ids_allowed(user_service, mock_repository, mock_user_types_repository):
    user_id = uuid4()
    group_id = uuid4()
    update_data = UserUpdate(role_ids=[], user_type_id=CONSOLE_TYPE_ID, group_id=group_id)
    updated_user = _user(user_id, _user_type(CONSOLE_TYPE_ID, "console"), group_id=group_id)
    mock_user_types_repository.get_by_id.return_value = _user_type(CONSOLE_TYPE_ID, "console")
    mock_repository.update.return_value = updated_user
    mock_repository.get_full.return_value = updated_user

    result = await user_service.update(user_id, update_data)

    mock_user_types_repository.get_by_id.assert_called_once_with(CONSOLE_TYPE_ID)
    mock_repository.update.assert_called_once_with(user_id, update_data)
    assert update_data.role_ids == []
    assert result.group_id == group_id

@pytest.mark.asyncio
async def test_update_console_user_empty_role_ids_without_type_allowed(user_service, mock_repository, mock_user_types_repository):
    user_id = uuid4()
    update_data = UserUpdate(role_ids=[])
    console_user = _user(user_id, _user_type(CONSOLE_TYPE_ID, "console"))
    mock_repository.get_full.return_value = console_user
    mock_repository.update.return_value = console_user

    result = await user_service.update(user_id, update_data)

    mock_user_types_repository.get_by_id.assert_not_called()
    mock_repository.update.assert_called_once_with(user_id, update_data)
    assert result == console_user

@pytest.mark.asyncio
async def test_update_user_empty_role_ids(user_service, mock_repository):
    user_id = uuid4()
    update_data = UserUpdate(role_ids=[])
    mock_repository.get_full.return_value = _user(user_id, _user_type(INTERACTIVE_TYPE_ID, "interactive"))

    with pytest.raises(AppException) as exc_info:
        await user_service.update(user_id, update_data)

    assert exc_info.value.error_key == ErrorKey.USER_ROLES_REQUIRED
    assert exc_info.value.status_code == 400
    mock_repository.update.assert_not_called()

@pytest.mark.asyncio
async def test_update_console_to_interactive_empty_role_ids_rejected(user_service, mock_repository, mock_user_types_repository):
    user_id = uuid4()
    update_data = UserUpdate(role_ids=[], user_type_id=INTERACTIVE_TYPE_ID)
    mock_repository.get_full.return_value = _user(user_id, _user_type(CONSOLE_TYPE_ID, "console"))
    mock_user_types_repository.get_by_id.return_value = _user_type(INTERACTIVE_TYPE_ID, "interactive")

    with pytest.raises(AppException) as exc_info:
        await user_service.update(user_id, update_data)

    assert exc_info.value.error_key == ErrorKey.USER_ROLES_REQUIRED
    mock_repository.update.assert_not_called()

@pytest.mark.asyncio
async def test_update_roleless_console_to_interactive_without_role_ids_rejected(user_service, mock_repository, mock_user_types_repository):
    user_id = uuid4()
    update_data = UserUpdate(user_type_id=INTERACTIVE_TYPE_ID)
    mock_repository.get_full.return_value = _user(user_id, _user_type(CONSOLE_TYPE_ID, "console"))
    mock_user_types_repository.get_by_id.return_value = _user_type(INTERACTIVE_TYPE_ID, "interactive")

    with pytest.raises(AppException) as exc_info:
        await user_service.update(user_id, update_data)

    assert exc_info.value.error_key == ErrorKey.USER_ROLES_REQUIRED
    assert exc_info.value.status_code == 400
    mock_repository.update.assert_not_called()

@pytest.mark.asyncio
async def test_update_roleless_console_keeping_console_type_allowed(user_service, mock_repository, mock_user_types_repository):
    user_id = uuid4()
    update_data = UserUpdate(user_type_id=CONSOLE_TYPE_ID, email="console@example.com")
    console_user = _user(user_id, _user_type(CONSOLE_TYPE_ID, "console"))
    mock_repository.get_by_email.return_value = None
    mock_repository.get_full.return_value = console_user
    mock_repository.update.return_value = console_user
    mock_user_types_repository.get_by_id.return_value = _user_type(CONSOLE_TYPE_ID, "console")

    result = await user_service.update(user_id, update_data)

    mock_repository.update.assert_called_once_with(user_id, update_data)
    assert result == console_user

@pytest.mark.asyncio
async def test_update_user_empty_role_ids_unknown_user_type(user_service, mock_repository, mock_user_types_repository):
    user_id = uuid4()
    update_data = UserUpdate(role_ids=[], user_type_id=uuid4())
    mock_user_types_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as exc_info:
        await user_service.update(user_id, update_data)

    assert exc_info.value.error_key == ErrorKey.USER_TYPE_NOT_FOUND
    mock_repository.update.assert_not_called()

@pytest.mark.asyncio
async def test_update_user_duplicate_email(user_service, mock_repository):
    user_id = uuid4()
    other_id = uuid4()
    update_data = UserUpdate(email="taken@example.com")
    mock_repository.get_by_email.return_value = MagicMock(id=other_id)

    with pytest.raises(AppException) as exc_info:
        await user_service.update(user_id, update_data)

    assert exc_info.value.error_key == ErrorKey.EMAIL_ALREADY_EXISTS
    mock_repository.get_by_email.assert_called_once_with(
        update_data.email, include_deleted=True
    )
    mock_repository.update.assert_not_called()

@pytest.mark.asyncio
async def test_update_user_entra_oid_conflict(user_service, mock_repository):
    user_id = uuid4()
    other_id = uuid4()
    update_data = UserUpdate(entra_oid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    mock_repository.get_by_entra_oid.return_value = MagicMock(id=other_id)

    with pytest.raises(AppException) as exc_info:
        await user_service.update(user_id, update_data)

    assert exc_info.value.error_key == ErrorKey.ENTRA_OID_IN_USE
    assert exc_info.value.status_code == 409
    mock_repository.get_by_entra_oid.assert_called_once_with(update_data.entra_oid)
    mock_repository.update.assert_not_called()

@pytest.mark.asyncio
async def test_update_user_entra_oid_same_user_allowed(user_service, mock_repository):
    user_id = uuid4()
    oid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    update_data = UserUpdate(entra_oid=oid)
    mock_repository.get_by_entra_oid.return_value = MagicMock(id=user_id)
    mock_updated_user = UserRead(
        id=user_id,
        username="testuser",
        email="test@example.com",
        is_active=1,
        roles=[],
        user_type=UserTypeRead(
            id=UUID("00000196-edb1-2b80-a681-167fc2a697dd"),
            name="interactive",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        api_keys=[],
        entra_oid=oid,
    )
    mock_repository.update.return_value = mock_updated_user
    mock_repository.get_full.return_value = mock_updated_user

    result = await user_service.update(user_id, update_data)

    mock_repository.get_by_entra_oid.assert_called_once_with(oid)
    mock_repository.update.assert_called_once_with(user_id, update_data)
    assert result == mock_updated_user

@pytest.mark.asyncio
async def test_get_all_users(user_service, mock_repository):
    # Setup
    mock_users = [
        MagicMock(id=uuid4(), username=f"user{i}", email=f"user{i}@example.com")
        for i in range(3)
    ]
    mock_repository.get_all.return_value = mock_users

    # Execute
    filter_model = BaseFilterModel(skip=0, limit=10)
    result = await user_service.get_all(filter_model)

    # Assert
    mock_repository.get_all.assert_called_once_with(filter_model)
    assert result == mock_users