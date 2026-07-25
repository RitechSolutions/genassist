"""Integration tests for the LLM usage control-plane endpoints"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.llm_usage import CONTROL_SINGLETON_KEY
from app.services.llm_usage_control import SHADOW_QUALIFYING_WINDOW_DAYS
from app.services.llm_usage_recorder import LlmUsageRecorder

BASE = "/api/analytics/llm-usage"
CONTROL_URL = f"{BASE}/control"
CAPTURE_URL = f"{BASE}/capture"
SHADOW_URL = f"{BASE}/shadow/start"
CUTOVER_URL = f"{BASE}/cutover"


@pytest_asyncio.fixture
async def control_db():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def reset():
        async with maker() as session:
            await session.execute(
                text(
                    "UPDATE llm_usage_control SET capture_enabled=false, capture_started_at=NULL, "
                    "ledger_cutover_enabled=false, shadow_started_at=NULL, shadow_passed_at=NULL "
                    "WHERE singleton_key=:k"
                ),
                {"k": CONTROL_SINGLETON_KEY},
            )
            await session.execute(text("DELETE FROM llm_usage_reconciliation_reports"))
            await session.commit()

    await reset()
    try:
        yield maker
    finally:
        await reset()
        await engine.dispose()


async def _seed_shadow_passed(maker, passing_days: int, total_days: int) -> None:
    async with maker() as session:
        await session.execute(
            text("UPDATE llm_usage_control SET shadow_passed_at=now() WHERE singleton_key=:k"),
            {"k": CONTROL_SINGLETON_KEY},
        )
        base = date(2026, 1, 1)
        for i in range(total_days):
            await session.execute(
                text(
                    "INSERT INTO llm_usage_reconciliation_reports (id, report_date, passed, is_deleted) "
                    "VALUES (:id, :d, :p, 0)"
                ),
                {"id": uuid4(), "d": base + timedelta(days=i), "p": i < passing_days},
            )
        await session.commit()


@pytest.mark.asyncio
async def test_get_control_inert(authorized_client, control_db):
    resp = authorized_client.get(CONTROL_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["capture_enabled"] is False
    assert body["capture_started_at"] is None
    assert body["ledger_cutover_enabled"] is False
    assert body["cost_source"] == "daily_stats"


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


@pytest.mark.asyncio
async def test_shadow_start_requires_capture(authorized_client, control_db):
    resp = authorized_client.post(SHADOW_URL)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_shadow_start_and_conflict(authorized_client, control_db):
    authorized_client.post(CAPTURE_URL)

    started = authorized_client.post(SHADOW_URL)
    assert started.status_code == 200
    assert started.json()["shadow_started_at"] is not None

    again = authorized_client.post(SHADOW_URL)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_cutover_disable_always_allowed(authorized_client, control_db):
    resp = authorized_client.post(CUTOVER_URL, json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["ledger_cutover_enabled"] is False


@pytest.mark.asyncio
async def test_cutover_enable_requires_capture(authorized_client, control_db):
    resp = authorized_client.post(CUTOVER_URL, json={"enabled": True})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cutover_enable_requires_shadow_pass(authorized_client, control_db):
    authorized_client.post(CAPTURE_URL)
    resp = authorized_client.post(CUTOVER_URL, json={"enabled": True})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cutover_enable_blocked_when_window_incomplete(authorized_client, control_db):
    authorized_client.post(CAPTURE_URL)
    await _seed_shadow_passed(control_db, passing_days=3, total_days=3)
    resp = authorized_client.post(CUTOVER_URL, json={"enabled": True})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cutover_enable_success_flips_cost_source(authorized_client, control_db):
    authorized_client.post(CAPTURE_URL)
    await _seed_shadow_passed(
        control_db, passing_days=SHADOW_QUALIFYING_WINDOW_DAYS, total_days=SHADOW_QUALIFYING_WINDOW_DAYS
    )
    resp = authorized_client.post(CUTOVER_URL, json={"enabled": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ledger_cutover_enabled"] is True
    assert body["cost_source"] == "llm_usage_ledger"
