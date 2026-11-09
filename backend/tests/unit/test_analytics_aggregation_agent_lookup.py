"""Unit tests for the agent lookup behind the finalize and thumbs analytics writes"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, Table, insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette_context import request_cycle_context

from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationModel
from app.repositories.analytics_aggregation import AnalyticsAggregationRepository


def _table(model, *columns):
    return Table(model.__tablename__, MetaData(), *(model.__table__.c[name]._copy() for name in columns))


@pytest.mark.asyncio
async def test_finds_the_agent_for_a_non_admin_caller_who_created_neither_row():
    agent_id, operator_id, conversation_id = uuid4(), uuid4(), uuid4()
    agents = _table(AgentModel, "id", "operator_id", "created_by", "is_deleted")
    conversations = _table(ConversationModel, "id", "operator_id", "created_by", "group_id", "is_deleted")
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(agents.create)
            await conn.run_sync(conversations.create)
            await conn.execute(
                insert(agents).values(id=agent_id, operator_id=operator_id, created_by=uuid4(), is_deleted=0)
            )
            await conn.execute(
                insert(conversations).values(
                    id=conversation_id, operator_id=operator_id, created_by=uuid4(), group_id=None, is_deleted=0
                )
            )

        caller = {
            "user_id": uuid4(),
            "group_id": None,
            "supervised_group_ids": [],
            "user_roles": [SimpleNamespace(name="operator")],
        }
        async with AsyncSession(engine) as session:
            with request_cycle_context(caller):
                found = await AnalyticsAggregationRepository(session).get_agent_id_for_conversation(conversation_id)
    finally:
        await engine.dispose()

    assert found == agent_id
