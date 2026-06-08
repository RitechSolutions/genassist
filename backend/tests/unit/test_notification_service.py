from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions.exception_classes import AppException
from app.repositories.notification import NotificationRepository
from app.schemas.notification import NotificationUserSettingsUpdate
from app.services.notification import NotificationService


@pytest.fixture
def mock_repository():
    return AsyncMock(spec=NotificationRepository)


@pytest.fixture
def notification_service(mock_repository):
    return NotificationService(repo=mock_repository)


@pytest.mark.asyncio
async def test_get_user_settings_uses_json_keyed_user_settings(
    notification_service: NotificationService,
    mock_repository: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("app.services.notification.current_user_is_admin", lambda: False)
    user_id = uuid4()

    types = {
        "conversation_started": SimpleNamespace(id=uuid4(), is_tenant=False, is_enabled=True),
        "conversation_hostility": SimpleNamespace(id=uuid4(), is_tenant=False, is_enabled=True),
        "conversation_finalized_hostility": SimpleNamespace(
            id=uuid4(), is_tenant=False, is_enabled=True
        ),
        "workflow_failed": SimpleNamespace(id=uuid4(), is_tenant=True, is_enabled=True),
    }
    mock_repository.ensure_notification_types.return_value = types
    mock_repository.list_user_notification_settings.return_value = {
        "conversation_started": False,
        "conversation_hostility": True,
    }
    mock_repository.build_audience_flags_for_user.return_value = {
        "conversation_started": True,
        "conversation_hostility": True,
        "conversation_finalized_hostility": False,
        "workflow_failed": True,
    }

    result = await notification_service.get_user_settings(
        user_id, user_group_id=None, supervised_group_ids=[]
    )

    assert result.conversation_started is False
    assert result.conversation_hostility is True
    assert result.conversation_finalized_hostility is False
    assert result.workflow_failed is True
    assert result.can_manage_workflow_failed is False


@pytest.mark.asyncio
async def test_update_user_settings_calls_repo_with_type_key(
    notification_service: NotificationService,
    mock_repository: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("app.services.notification.current_user_is_admin", lambda: False)
    user_id = uuid4()

    types = {
        "conversation_started": SimpleNamespace(id=uuid4(), is_tenant=False, is_enabled=True),
        "conversation_hostility": SimpleNamespace(id=uuid4(), is_tenant=False, is_enabled=True),
        "conversation_finalized_hostility": SimpleNamespace(
            id=uuid4(), is_tenant=False, is_enabled=True
        ),
        "workflow_failed": SimpleNamespace(id=uuid4(), is_tenant=True, is_enabled=True),
    }
    mock_repository.ensure_notification_types.return_value = types
    mock_repository.get_user_settings = AsyncMock()
    mock_repository.list_user_notification_settings.return_value = {}
    mock_repository.build_audience_flags_for_user.return_value = {
        "conversation_started": True,
        "conversation_hostility": True,
        "conversation_finalized_hostility": True,
        "workflow_failed": False,
    }

    dto = NotificationUserSettingsUpdate(conversation_started=False)
    await notification_service.update_user_settings(
        user_id, dto, user_group_id=None, supervised_group_ids=[]
    )

    mock_repository.upsert_user_notification_setting.assert_awaited_once_with(
        user_id=user_id,
        type_key="conversation_started",
        is_enabled=False,
    )


@pytest.mark.asyncio
async def test_update_user_settings_rejects_non_admin_tenant_change(
    notification_service: NotificationService,
    mock_repository: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("app.services.notification.current_user_is_admin", lambda: False)

    mock_repository.ensure_notification_types.return_value = {
        "conversation_started": SimpleNamespace(id=uuid4(), is_tenant=False, is_enabled=True),
        "conversation_hostility": SimpleNamespace(id=uuid4(), is_tenant=False, is_enabled=True),
        "conversation_finalized_hostility": SimpleNamespace(
            id=uuid4(), is_tenant=False, is_enabled=True
        ),
        "workflow_failed": SimpleNamespace(id=uuid4(), is_tenant=True, is_enabled=True),
    }

    with pytest.raises(AppException) as exc:
        await notification_service.update_user_settings(
            uuid4(),
            NotificationUserSettingsUpdate(workflow_failed=False),
            user_group_id=None,
            supervised_group_ids=[],
        )
    assert exc.value.status_code == 403
