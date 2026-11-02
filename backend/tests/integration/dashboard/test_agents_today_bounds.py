from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationModel
from app.repositories.dashboard import DashboardRepository


@pytest_asyncio.fixture
async def db(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_client_today_bounds_replace_the_server_utc_day(db):
    rows = (
        await db.execute(
            select(AgentModel.id, AgentModel.operator_id)
            .where(AgentModel.is_deleted == 0)
            .order_by(AgentModel.name)
            .limit(5)
        )
    ).all()
    agent = next((row for row in rows if row.operator_id), None)
    if agent is None:
        pytest.skip("need a listed agent with an operator to count conversations for")

    repo = DashboardRepository(db)
    utc_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    west_today = {
        "today_start": utc_midnight - timedelta(hours=2),
        "today_end": utc_midnight + timedelta(hours=22),
    }

    async def count(**bounds):
        stats = await repo.get_agents_with_stats(limit=5, **bounds)
        return next(row["conversations_today"] for row in stats if row["id"] == agent.id)

    def add_conversation(at):
        db.add(
            ConversationModel(
                id=uuid4(),
                operator_id=agent.operator_id,
                conversation_type="chat",
                conversation_date=at,
            )
        )

    server_before = await count()
    west_before = await count(**west_today)

    add_conversation(utc_midnight - timedelta(hours=1))
    await db.flush()
    assert await count() == server_before
    assert await count(**west_today) == west_before + 1

    add_conversation(utc_midnight + timedelta(hours=23))
    await db.flush()
    assert await count() == server_before + 1
    assert await count(**west_today) == west_before + 1
