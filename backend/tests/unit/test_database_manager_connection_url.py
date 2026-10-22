import pytest

from app.modules.integration.database import database_manager
from app.modules.integration.database.database_manager import DatabaseManager


@pytest.mark.asyncio
@pytest.mark.parametrize("db_type, port", [("postgresql", 5432), ("mysql", 3306)])
async def test_password_with_at_and_colon_reaches_the_driver_intact(monkeypatch, db_type, port):
    monkeypatch.setattr(database_manager, "decrypt_key", lambda value: value)
    manager = DatabaseManager(
        {
            "database_type": db_type,
            "database_host": "db.example.com",
            "database_port": port,
            "database_name": "core",
            "database_user": "genassist",
            "database_password": "Sup3r@Secret:99",
        }
    )
    await manager.connect()
    try:
        url = manager.engine.url
        assert url.username == "genassist"
        assert url.password == "Sup3r@Secret:99"
        assert url.host == "db.example.com"
        assert url.port == port
        assert url.database == "core"
    finally:
        await manager.disconnect()
