"""The login-only /webhooks CRUD API must not reach Webhook Trigger endpoints.

Those rows are managed through /workflow-triggers, which enforces Workflow
permissions; the generic routes treat them as not found and refuse to create
or convert a webhook into one.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

# Importing app.services.webhook first hits a pre-existing circular import
# (via chat_as_client_use_case); going through the route module avoids it.
import app.api.v1.routes.webhook  # noqa: F401
from app.schemas.webhook import WebhookCreate, WebhookUpdate
from app.services.webhook import WebhookService


def _service(row):
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=row)
    repo.update = AsyncMock(return_value=row)
    repo.delete = AsyncMock(return_value=True)
    repo.create = AsyncMock(return_value=row)
    return WebhookService(repo, MagicMock()), repo


TRIGGER = SimpleNamespace(webhook_type="workflow_trigger", secret="enc")
GENERIC = SimpleNamespace(webhook_type="generic", secret=None)


@pytest.mark.asyncio
async def test_trigger_rows_are_hidden_from_generic_crud():
    service, repo = _service(TRIGGER)
    wid = uuid4()

    assert await service.get_webhook_by_id(wid, decrypt_sensitive=True) is None
    assert await service.update_webhook(wid, WebhookUpdate(secret="x", is_active=0)) is None
    assert await service.delete_webhook(wid) is False
    repo.update.assert_not_awaited()
    repo.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_generic_rows_still_work():
    service, repo = _service(GENERIC)
    wid = uuid4()

    assert await service.get_webhook_by_id(wid) is GENERIC
    assert await service.update_webhook(wid, WebhookUpdate(name="n")) is GENERIC
    assert await service.delete_webhook(wid) is True


@pytest.mark.asyncio
async def test_cannot_create_or_convert_to_trigger_type():
    service, repo = _service(GENERIC)

    with pytest.raises(HTTPException) as e:
        await service.create_webhook(
            WebhookCreate(name="n", webhook_type="workflow_trigger"), "http://x"
        )
    assert e.value.status_code == 400

    with pytest.raises(HTTPException) as e:
        await service.update_webhook(uuid4(), WebhookUpdate(webhook_type="workflow_trigger"))
    assert e.value.status_code == 400
    repo.create.assert_not_awaited()
    repo.update.assert_not_awaited()
