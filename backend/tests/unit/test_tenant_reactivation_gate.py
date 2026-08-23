"""Reactivating a tenant proves its database first.

Startup migrates and verifies active tenants only, so a tenant that sat inactive through
a deployment keeps the schema it had then. Flipping is_active back on would put that stale
database straight back into service, where the recorder logs failed billing inserts
instead of raising them.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import migrations
from app.repositories.tenant import TenantRepository
from app.services.tenant import TenantService


@pytest.fixture(autouse=True)
def _multi_tenant_on(monkeypatch):
    from app.core.config.settings import settings

    monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)


@pytest.fixture
def service():
    repository = AsyncMock(spec=TenantRepository)
    repository.db = AsyncMock()
    return TenantService(repository=repository)


def _tenant(is_active: bool):
    return SimpleNamespace(id=uuid4(), slug="acme", name="Acme", is_active=is_active)


@pytest.fixture
def gate(monkeypatch):
    def _install(ok: bool):
        checked = MagicMock(return_value=ok)
        monkeypatch.setattr(migrations, "migrate_and_verify_tenant", checked)
        return checked

    return _install


@pytest.mark.asyncio
class TestReactivation:
    async def test_a_verified_database_is_reactivated(self, service, gate):
        checked = gate(ok=True)
        tenant = _tenant(is_active=False)
        service.repository.get_by_id.return_value = tenant

        result = await service.update_tenant(tenant.id, is_active=True)

        checked.assert_called_once_with("acme")
        assert result is tenant and tenant.is_active is True
        service.repository.db.commit.assert_awaited_once()

    async def test_an_unverified_database_refuses_and_stays_inactive(self, service, gate):
        gate(ok=False)
        tenant = _tenant(is_active=False)
        service.repository.get_by_id.return_value = tenant

        result = await service.update_tenant(tenant.id, is_active=True)

        assert isinstance(result, ValueError) and "acme" in result.args[0]
        assert tenant.is_active is False, "the refusal must not leave a half-applied update"
        service.repository.db.commit.assert_not_awaited()

    async def test_the_refusal_survives_other_fields_in_the_same_request(self, service, gate):
        gate(ok=False)
        tenant = _tenant(is_active=False)
        service.repository.get_by_id.return_value = tenant

        result = await service.update_tenant(tenant.id, name="Renamed", is_active=True)

        assert isinstance(result, ValueError)
        assert tenant.name == "Acme", "nothing is written when reactivation is refused"


@pytest.mark.asyncio
class TestUpdatesThatAreNotReactivation:
    """The gate costs a migration run, so it must fire only on the transition"""

    async def test_an_already_active_tenant_is_not_re_migrated(self, service, gate):
        checked = gate(ok=True)
        service.repository.get_by_id.return_value = _tenant(is_active=True)

        await service.update_tenant(uuid4(), is_active=True)

        checked.assert_not_called()

    async def test_deactivating_is_not_gated(self, service, gate):
        checked = gate(ok=True)
        service.repository.get_by_id.return_value = _tenant(is_active=True)

        await service.update_tenant(uuid4(), is_active=False)

        checked.assert_not_called()

    async def test_a_plain_rename_is_not_gated(self, service, gate):
        checked = gate(ok=True)
        service.repository.get_by_id.return_value = _tenant(is_active=False)

        await service.update_tenant(uuid4(), name="Renamed")

        checked.assert_not_called()

    async def test_a_missing_tenant_never_reaches_the_gate(self, service, gate):
        checked = gate(ok=True)
        service.repository.get_by_id.return_value = None

        assert await service.update_tenant(uuid4(), is_active=True) is None
        checked.assert_not_called()


@pytest.mark.asyncio
class TestMigrateAndVerifyTenant:
    async def test_it_verifies_only_after_a_successful_migration(self, monkeypatch):
        order = []
        monkeypatch.setattr(migrations, "run_migrations", lambda url: order.append("migrate") or True)
        monkeypatch.setattr(migrations, "verify_llm_usage_schema", lambda url, label: order.append("verify") or True)

        assert migrations.migrate_and_verify_tenant("acme") is True
        assert order == ["migrate", "verify"]

    async def test_a_failed_migration_short_circuits(self, monkeypatch):
        monkeypatch.setattr(migrations, "run_migrations", lambda url: False)
        monkeypatch.setattr(
            migrations, "verify_llm_usage_schema", MagicMock(side_effect=AssertionError("must not verify"))
        )

        assert migrations.migrate_and_verify_tenant("acme") is False

    async def test_a_raising_migration_is_reported_not_propagated(self, monkeypatch):
        monkeypatch.setattr(migrations, "run_migrations", MagicMock(side_effect=OSError("database is gone")))

        assert migrations.migrate_and_verify_tenant("acme") is False
