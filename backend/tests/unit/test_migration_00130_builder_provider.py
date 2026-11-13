"""Migration 00130: the Workflow Builder's own LLM provider, on tenants seeded before it existed"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "00130_add_workflow_builder_llm_provider.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_00130", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBind:
    """Records every statement; `respond(sql, params)` supplies what `.scalar()` returns"""

    def __init__(self, respond):
        self._respond = respond
        self.calls = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        params = dict(params or {})
        self.calls.append((sql, params))
        value = self._respond(sql, params)
        return SimpleNamespace(scalar=lambda: value)


@pytest.fixture
def migration(monkeypatch):
    def _install(respond):
        module = _load_migration()
        bind = FakeBind(respond)
        monkeypatch.setattr(module, "op", SimpleNamespace(get_bind=lambda: bind))
        return module, bind

    return _install


def _inserts(bind):
    return [c for c in bind.calls if c[0].startswith("INSERT INTO llm_providers")]


def _builder_repoints(bind):
    return [c for c in bind.calls if c[0].startswith("UPDATE workflows w")]


def _provider_updates(bind):
    return [c for c in bind.calls if c[0].startswith("UPDATE llm_providers")]


class TestUpgrade:
    def test_copies_the_seeded_key_then_points_the_builder_at_the_new_provider(self, migration):
        def respond(sql, params):
            if sql.startswith("SELECT is_deleted"):
                return None  # not there yet
            if "connection_data->>'api_key'" in sql and "id = CAST(:value AS uuid)" in sql:
                return "enc:openai-dev-key"
            return None

        module, bind = migration(respond)
        module.upgrade()

        (insert_sql, insert_params), = _inserts(bind)
        assert insert_params == {
            "id": module.PROVIDER_ID, "name": module.PROVIDER_NAME, "model": module.PROVIDER_MODEL,
            "key": "enc:openai-dev-key",
        }
        assert "'openai'" in insert_sql and "jsonb_build_object('api_key'" in insert_sql
        # is_active, is_default (never the tenant default), is_deleted
        assert "1, 0, 0, CURRENT_TIMESTAMP" in insert_sql

        (repoint_sql, repoint_params), = _builder_repoints(bind)
        assert repoint_params == {"provider_id": module.PROVIDER_ID, "agent_name": "Workflow Builder"}
        assert "n->>'type' = 'agentNode'" in repoint_sql and "'{data,providerId}'" in repoint_sql
        assert bind.calls.index(_inserts(bind)[0]) < bind.calls.index(_builder_repoints(bind)[0])

    def test_falls_back_to_the_tenants_oldest_active_openai_provider(self, migration):
        def respond(sql, params):
            if "connection_data->>'api_key'" in sql and params == {"value": "openai"}:
                return "enc:other-key"
            return None

        module, bind = migration(respond)
        module.upgrade()

        lookups = [p["value"] for s, p in bind.calls if "connection_data->>'api_key'" in s]
        assert lookups == [module.SOURCE_PROVIDER_ID, module.SOURCE_PROVIDER_NAME, "openai"]
        assert _inserts(bind)[0][1]["key"] == "enc:other-key"
        assert len(_builder_repoints(bind)) == 1

    def test_a_tenant_without_an_openai_key_is_left_alone(self, migration):
        module, bind = migration(lambda sql, params: None)
        module.upgrade()

        assert _inserts(bind) == [] and _builder_repoints(bind) == [] and _provider_updates(bind) == []

    def test_an_existing_provider_is_not_inserted_again_but_the_builder_is_still_repointed(self, migration):
        module, bind = migration(lambda sql, params: 0 if sql.startswith("SELECT is_deleted") else None)
        module.upgrade()

        assert _inserts(bind) == [] and _provider_updates(bind) == []
        assert _builder_repoints(bind)[0][1]["provider_id"] == module.PROVIDER_ID

    def test_a_soft_deleted_provider_is_revived_instead_of_duplicated(self, migration):
        module, bind = migration(lambda sql, params: 1 if sql.startswith("SELECT is_deleted") else None)
        module.upgrade()

        assert _inserts(bind) == []
        (sql, params), = _provider_updates(bind)
        assert "is_deleted = 0, is_active = 1, is_default = 0" in sql and "llm_model = :model" in sql
        assert params == {"id": module.PROVIDER_ID, "name": module.PROVIDER_NAME, "model": module.PROVIDER_MODEL}
        assert len(_builder_repoints(bind)) == 1


class TestDowngrade:
    def test_points_the_builder_back_and_soft_deletes_the_provider(self, migration):
        module, bind = migration(lambda sql, params: 1 if sql.startswith("SELECT 1 FROM llm_providers") else None)
        module.downgrade()

        assert _builder_repoints(bind)[0][1]["provider_id"] == module.SOURCE_PROVIDER_ID
        (sql, params), = _provider_updates(bind)
        assert "is_deleted = 1, is_default = 0" in sql and params == {"id": module.PROVIDER_ID}
        assert not any("DELETE" in s for s, _ in bind.calls), "a provider other rows may reference is never dropped"

    def test_without_the_original_provider_the_builder_keeps_its_pointer(self, migration):
        def respond(sql, params):
            if sql.startswith("SELECT 1 FROM llm_providers"):
                return 1 if params["id"] == _load_migration().PROVIDER_ID else None
            return None

        module, bind = migration(respond)
        module.downgrade()

        assert _builder_repoints(bind) == []
        assert len(_provider_updates(bind)) == 1

    def test_nothing_happens_when_the_provider_was_never_added(self, migration):
        module, bind = migration(lambda sql, params: None)
        module.downgrade()

        assert len(bind.calls) == 1 and _provider_updates(bind) == []


def test_the_literals_match_the_seed_config():
    from app.db.seed.seed_data_config import seed_test_data

    module = _load_migration()
    assert module.PROVIDER_ID == seed_test_data.workflow_builder_llm_provider_id
    assert module.PROVIDER_NAME == seed_test_data.workflow_builder_llm_provider_name
    assert module.PROVIDER_MODEL == seed_test_data.workflow_builder_llm_model
    assert module.SOURCE_PROVIDER_ID == seed_test_data.llm_provider_id
    assert module.down_revision == "9c4e1f7a2b6d"
