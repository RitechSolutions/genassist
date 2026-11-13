from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.auth.utils import hash_api_key
from app.core.utils.encryption_utils import decrypt_key, encrypt_key
from app.schemas.api_key import ApiKeyCreate, ApiKeyRotate
from app.services import api_keys as api_keys_module
from app.services.api_keys import ApiKeysService

STORED = "stored-ciphertext"
CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _row(key_val: str = STORED) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name="alpha key",
        is_active=1,
        user_id=uuid4(),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        roles=[],
        key_val=key_val,
        previous_hashed_expires_at=None,
        credential_expires_at=None,
        credential_expiry_days=None,
    )


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(api_keys_module, "context", {"user_roles": [], "user_id": uuid4()})
    audit_db = SimpleNamespace(add=MagicMock(), commit=AsyncMock())
    return ApiKeysService(
        repository=AsyncMock(),
        roles_repository=AsyncMock(),
        audit_log_repository=SimpleNamespace(db=audit_db),
    )


@pytest.mark.asyncio
async def test_create_returns_the_secret_and_keeps_the_stored_value(service):
    row = _row()
    service.repository.create.return_value = row

    result = await service.create(ApiKeyCreate(name="alpha key", role_ids=[]))

    _, encrypted, hashed = service.repository.create.await_args.args
    secret_matches_stored_hash = hash_api_key(result.key_val) == hashed
    stored_value_is_encrypted = encrypted != result.key_val and decrypt_key(encrypted) == result.key_val
    row_keeps_stored_value = row.key_val == STORED
    assert secret_matches_stored_hash
    assert stored_value_is_encrypted
    assert row_keeps_stored_value


@pytest.mark.asyncio
async def test_rotate_returns_the_new_secret_and_keeps_the_stored_value(service):
    row = _row()
    service.repository.get_by_id.return_value = row
    service.repository.rotate_credentials.return_value = row

    result = await service.rotate(row.id, ApiKeyRotate(overlap_seconds=3600))

    _, _, encrypted, hashed, overlap_seconds = service.repository.rotate_credentials.await_args.args
    secret_matches_stored_hash = hash_api_key(result.key_val) == hashed
    stored_value_is_encrypted = encrypted != result.key_val and decrypt_key(encrypted) == result.key_val
    row_keeps_stored_value = row.key_val == STORED
    assert secret_matches_stored_hash
    assert stored_value_is_encrypted
    assert row_keeps_stored_value
    assert overlap_seconds == 3600


@pytest.mark.asyncio
@pytest.mark.parametrize("encrypted_at_rest", [True, False], ids=["encrypted", "legacy-plaintext"])
async def test_reveal_returns_the_secret_and_keeps_the_stored_value(service, encrypted_at_rest):
    stored = encrypt_key("revealed-secret") if encrypted_at_rest else "revealed-secret"
    row = _row(stored)
    service.repository.get_by_id.return_value = row

    result = await service.reveal(row.id)

    audit_db = service.audit_log_repository.db
    assert result.key_val == "revealed-secret"
    assert row.key_val == stored
    assert audit_db.add.call_args.args[0].action_name == "Reveal"
    audit_db.commit.assert_awaited_once()
