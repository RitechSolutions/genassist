"""Where the physical-schema check runs, and why the ordering matters.

A fresh database gets its tables from ``create_all`` at lifespan startup, not from
Alembic — ``run_migrations`` stamps head and creates nothing. Verifying before that point
fails on a database that is simply not built yet, and because uvicorn never starts, the
lifespan that would have built it never runs either. So the check belongs after
``multi_tenant_manager.initialize()`` and before the lifespan yields.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app as app_package
import migrations


class TestFreshDatabaseTenantMigrations:
    """Tenant discovery reads a `tenants` table a fresh master database does not have yet"""

    @pytest.fixture(autouse=True)
    def _multi_tenant_on(self, monkeypatch):
        from app.core.config.settings import settings

        monkeypatch.setattr(settings, "MULTI_TENANT_ENABLED", True)

    def test_an_uninitialized_master_skips_tenant_migrations_without_failing(self, monkeypatch):
        monkeypatch.setattr(migrations, "get_table_names", lambda url: ["alembic_version"])
        monkeypatch.setattr(
            migrations, "active_tenant_slugs", MagicMock(side_effect=AssertionError("must not be queried"))
        )

        assert migrations.run_migrations_for_all_tenants() is True

    def test_an_unreachable_master_reads_as_uninitialized(self, monkeypatch):
        monkeypatch.setattr(migrations, "get_table_names", MagicMock(side_effect=OSError("connection refused")))

        assert migrations.master_database_is_initialized() is False

    def test_an_initialized_master_still_migrates_its_tenants(self, monkeypatch):
        migrated = []
        monkeypatch.setattr(migrations, "get_table_names", lambda url: ["users", "tenants"])
        monkeypatch.setattr(migrations, "active_tenant_slugs", lambda: ["acme"])
        monkeypatch.setattr(migrations, "run_migrations", lambda url: migrated.append(url) or True)

        assert migrations.run_migrations_for_all_tenants() is True
        assert len(migrated) == 1


@pytest.mark.asyncio
class TestLifespanVerifies:
    """The lifespan is the only place the schema is guaranteed to exist"""

    @pytest.fixture
    def lifespan(self, monkeypatch):
        from app.core import permissions
        from app.db import multi_tenant_session
        from app.dependencies import tenant_dependencies

        calls = []

        monkeypatch.setattr(app_package, "output_open_api", AsyncMock())
        monkeypatch.setattr(app_package, "_initialize_redis_services", AsyncMock(return_value=(None, None)))
        monkeypatch.setattr(app_package, "_initialize_websocket_services", AsyncMock())
        monkeypatch.setattr(
            multi_tenant_session.multi_tenant_manager,
            "initialize",
            AsyncMock(side_effect=lambda: calls.append("initialize")),
        )
        monkeypatch.setattr(
            tenant_dependencies, "pre_wormup_tenant_singleton", AsyncMock(side_effect=lambda: calls.append("warmup"))
        )
        monkeypatch.setattr(
            permissions, "sync_permissions_on_startup", AsyncMock(side_effect=lambda: calls.append("permissions"))
        )

        def _install(verified: bool):
            def _verify():
                calls.append("verify")
                return verified

            monkeypatch.setattr(migrations, "verify_llm_usage_schema_for_all_databases", _verify)
            return calls

        return _install

    async def test_a_sound_schema_lets_startup_finish(self, lifespan):
        calls = lifespan(verified=True)

        async with app_package._lifespan(MagicMock()):
            pass

        assert "verify" in calls

    async def test_verification_happens_after_the_schema_is_created(self, lifespan):
        """create_all runs inside initialize(), so verifying first would fail a fresh database"""
        calls = lifespan(verified=True)

        async with app_package._lifespan(MagicMock()):
            pass

        assert calls.index("initialize") < calls.index("verify")

    async def test_an_unverified_schema_refuses_to_serve(self, lifespan):
        lifespan(verified=False)

        with pytest.raises(RuntimeError) as excinfo:
            async with app_package._lifespan(MagicMock()):
                pytest.fail("the application must not start serving")

        assert "refusing to serve" in str(excinfo.value)

    async def test_a_failed_check_stops_before_the_remaining_startup_work(self, lifespan):
        calls = lifespan(verified=False)

        with pytest.raises(RuntimeError):
            async with app_package._lifespan(MagicMock()):
                pass

        assert "permissions" not in calls and "warmup" not in calls
