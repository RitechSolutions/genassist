"""Integration tests for the LLM usage control-plane endpoints"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.llm_usage import CONTROL_SINGLETON_KEY
from app.services.llm_usage_recorder import LlmUsageRecorder

BASE = "/api/analytics/llm-usage"
CONTROL_URL = f"{BASE}/control"
CAPTURE_URL = f"{BASE}/capture"


@pytest_asyncio.fixture
async def control_db():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def set_capture(enabled: bool):
        async with maker() as session:
            await session.execute(
                text(
                    "UPDATE llm_usage_control SET capture_enabled=:on, "
                    "capture_started_at=CASE WHEN :on THEN now() ELSE NULL END "
                    "WHERE singleton_key=:k"
                ),
                {"on": enabled, "k": CONTROL_SINGLETON_KEY},
            )
            await session.commit()

    await set_capture(False)
    try:
        yield maker
    finally:
        await set_capture(True)
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_control_inert(authorized_client, control_db):
    resp = authorized_client.get(CONTROL_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["capture_enabled"] is False
    assert body["capture_started_at"] is None


@pytest.mark.asyncio
async def test_capture_activation_one_way_idempotent(authorized_client, control_db):
    first = authorized_client.post(CAPTURE_URL)
    assert first.status_code == 200
    b1 = first.json()
    assert b1["capture_enabled"] is True
    assert b1["capture_started_at"] is not None
    stamp = b1["capture_started_at"]

    second = authorized_client.post(CAPTURE_URL)
    assert second.status_code == 200
    b2 = second.json()
    assert b2["capture_enabled"] is True
    assert b2["capture_started_at"] == stamp


@pytest.mark.asyncio
async def test_recorder_inert_until_activation(authorized_client, control_db):
    recorder = LlmUsageRecorder()
    async with control_db() as session:
        assert await recorder._capture_enabled(session) is False

    authorized_client.post(CAPTURE_URL)

    async with control_db() as session:
        assert await recorder._capture_enabled(session) is True
