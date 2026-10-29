import pytest

from app.modules.integration.database import database_manager
from app.modules.integration.database.database_manager import DatabaseManager


@pytest.mark.asyncio
@pytest.mark.parametrize("db_type, port", [("postgresql", 5432), ("mysql", 3306)])
@pytest.mark.parametrize(
    "saved_password, driver_password",
    [("Sup3r@Secret:99", "Sup3r@Secret:99"), ("p%40ss", "p@ss")],
)
async def test_saved_password_reaches_the_driver_intact(monkeypatch, db_type, port, saved_password, driver_password):
    monkeypatch.setattr(database_manager, "decrypt_key", lambda value: value)
    manager = DatabaseManager(
        {
            "database_type": db_type,
            "database_host": "db.example.com",
            "database_port": port,
            "database_name": "core",
            "database_user": "genassist",
            "database_password": saved_password,
        }
    )
    await manager.connect()
    try:
        url = manager.engine.url
        assert url.username == "genassist"
        assert url.password == driver_password
        assert url.host == "db.example.com"
        assert url.port == port
        assert url.database == "core"
    finally:
        await manager.disconnect()
