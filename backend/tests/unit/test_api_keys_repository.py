from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.api_keys import ApiKeysRepository
from app.schemas.api_key import ApiKeyUpdate


@pytest.fixture
def repository():
    repo = ApiKeysRepository(db=AsyncMock())
    repo.db.add = MagicMock()
    return repo


def _key(name: str) -> SimpleNamespace:
    # A plain stand-in for ApiKeyModel: instantiating the real ORM class here
    # would configure every mapper in the registry, which these tests don't need.
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        is_active=1,
        credential_expiry_days=None,
        credential_expires_at=None,
        updated_by=None,
    )


@pytest.mark.asyncio
async def test_update_rejects_rename_to_an_active_keys_name(repository):
    key = _key("alpha")
    repository.get_by_id = AsyncMock(return_value=key)
    repository._get_by_name = AsyncMock(return_value=_key("beta"))

    with pytest.raises(AppException) as exc:
        await repository.update(uuid4(), key.id, ApiKeyUpdate(name="beta"))

    assert exc.value.error_key == ErrorKey.API_KEY_NAME_EXISTS
    repository._get_by_name.assert_awaited_once_with("beta", exclude_id=key.id)
    assert key.name == "alpha"


@pytest.mark.asyncio
async def test_update_allows_rename_when_name_is_free(repository):
    key = _key("alpha")
    repository.get_by_id = AsyncMock(return_value=key)
    # A soft-deleted key with this name is filtered out by the session's
    # soft-delete criteria, so the lookup returns nothing and the name is free.
    repository._get_by_name = AsyncMock(return_value=None)

    await repository.update(uuid4(), key.id, ApiKeyUpdate(name="beta"))

    assert key.name == "beta"


@pytest.mark.asyncio
async def test_update_skips_name_lookup_when_name_unchanged(repository):
    key = _key("alpha")
    repository.get_by_id = AsyncMock(return_value=key)
    repository._get_by_name = AsyncMock()

    await repository.update(uuid4(), key.id, ApiKeyUpdate(name="alpha", is_active=0))

    repository._get_by_name.assert_not_awaited()
    assert key.is_active == 0
