import pytest


@pytest.mark.anyio
async def test_create_tenant_database_rejects_injection_slug_early(monkeypatch):
    """
    This test avoids requiring a real Postgres server by stubbing the SQLAlchemy
    engine and asserting an injection-like slug is rejected before any SQL executes.
    """

    from app.core.config.settings import settings
    from app.db import multi_tenant_session as mts

    executed = []

    class FakeIdentifierPreparer:
        def quote(self, ident: str) -> str:
            # Minimal Postgres-style identifier quoting.
            return '"' + ident.replace('"', '""') + '"'

    class FakeDialect:
        identifier_preparer = FakeIdentifierPreparer()

    class FakeConn:
        def execute(self, clause, params=None):
            sql_text = getattr(clause, "text", str(clause))
            executed.append((sql_text, params))

            class _Result:
                def fetchone(self_inner):
                    return None

            return _Result()

    class FakeConnectCtx:
        def __init__(self):
            self._conn = FakeConn()

        def __enter__(self):
            return self._conn

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeSyncEngine:
        dialect = FakeDialect()

        def connect(self):
            return FakeConnectCtx()

    def fake_create_engine(*args, **kwargs):
        return FakeSyncEngine()

    def fake_create_async_engine(*args, **kwargs):
        raise RuntimeError("stop-after-create-db")

    original_db_name = settings.DB_NAME
    try:
        settings.DB_NAME = "maindb"
        monkeypatch.setattr(mts, "create_engine", fake_create_engine)
        monkeypatch.setattr(mts, "create_async_engine", fake_create_async_engine)

        ok = await mts.multi_tenant_manager.create_tenant_database("x' OR 1=1;--")
        assert ok is False
        assert executed == [], "Invalid slugs should be rejected before SQL execution"
    finally:
        settings.DB_NAME = original_db_name


@pytest.mark.anyio
async def test_create_tenant_database_uses_bound_param_and_quotes_identifier(monkeypatch):
    """
    This test avoids requiring a real Postgres server by stubbing the SQLAlchemy
    engines and asserting on the SQL executed for the existence check and CREATE DATABASE.
    """

    from app.core.config.settings import settings
    from app.db import multi_tenant_session as mts

    executed = []

    class FakeIdentifierPreparer:
        def quote(self, ident: str) -> str:
            # Minimal Postgres-style identifier quoting.
            return '"' + ident.replace('"', '""') + '"'

    class FakeDialect:
        identifier_preparer = FakeIdentifierPreparer()

    class FakeConn:
        def execute(self, clause, params=None):
            sql_text = getattr(clause, "text", str(clause))
            executed.append((sql_text, params))

            class _Result:
                def fetchone(self_inner):
                    return None

            return _Result()

    class FakeConnectCtx:
        def __init__(self):
            self._conn = FakeConn()

        def __enter__(self):
            return self._conn

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeSyncEngine:
        dialect = FakeDialect()

        def connect(self):
            return FakeConnectCtx()

    def fake_create_engine(*args, **kwargs):
        return FakeSyncEngine()

    def fake_create_async_engine(*args, **kwargs):
        # Stop after CREATE DATABASE; schema creation is not under test here.
        raise RuntimeError("stop-after-create-db")

    original_db_name = settings.DB_NAME
    try:
        settings.DB_NAME = "maindb"
        monkeypatch.setattr(mts, "create_engine", fake_create_engine)
        monkeypatch.setattr(mts, "create_async_engine", fake_create_async_engine)

        ok = await mts.multi_tenant_manager.create_tenant_database("acme-co")
        assert ok is False  # expected due to stubbed async engine

        assert len(executed) >= 2, "Expected SELECT and CREATE DATABASE statements"

        select_sql, select_params = executed[0]
        assert "FROM pg_database" in select_sql
        assert ":db_name" in select_sql
        assert select_params == {
            "db_name": settings.get_tenant_database_name("acme-co"),
        }

        create_sql, create_params = executed[1]
        assert create_params is None
        assert create_sql.startswith("CREATE DATABASE ")

        # Ensure the identifier is quoted so special characters can't break SQL parsing.
        assert '"' in create_sql
        # DB name is identifier-quoted, never string-quoted.
        assert "'" not in create_sql
    finally:
        settings.DB_NAME = original_db_name

