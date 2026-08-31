"""Integration tests pinning that the custom-attributes backfill preserves conversations.updated_at"""

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi_injector import RequestScopeFactory
from sqlalchemy import delete, null, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette_context import context, request_cycle_context

from app.core.config.settings import settings
from app.core.tenant_scope import background_task_context, clear_tenant_context
from app.db.models.agent import AgentModel
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.conversation import ConversationModel
from app.db.models.message_model import TranscriptMessageModel
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.user import UserModel
from app.db.models.user_group import UserGroupModel
from app.db.models.workflow import WorkflowModel
from app.dependencies.injector import injector
from app.tasks.backfill_custom_attributes import backfill_custom_attributes_async

SEEDED_UPDATED_AT = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)

WORKFLOW_NODES = [
    {
        "id": "chat-input",
        "type": "chatInputNode",
        "data": {"inputSchema": {"customer_tier": {"useInFilter": True}}},
    }
]

RAW_RESPONSE_WITH_ATTRS = json.dumps(
    {
        "row_agent_response": {
            "state": {
                "nodeExecutionStatus": {"chat-input": {"type": "chatInputNode", "output": {"customer_tier": "gold"}}}
            }
        }
    }
)


@contextmanager
def acting_as(user_id):
    with request_cycle_context():
        context["user_id"] = user_id
        context["group_id"] = None
        context["supervised_group_ids"] = []
        context["user_roles"] = [SimpleNamespace(name="admin")]
        yield


class World:
    def __init__(self, maker):
        self.maker = maker
        self.group = None
        self.user = None
        self.statistics_id = None
        self.operator_id = None
        self.workflow_id = None
        self.agent_id = None
        self.message_ids = []
        self.updated_conversation_id = None
        self.no_attrs_conversation_id = None
        self.stale_conversation_id = None


@pytest_asyncio.fixture(loop_scope="module")
async def world(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    built = World(maker)

    async with maker() as session:
        snapshot = {
            row.id: (row.custom_attributes, row.updated_at)
            for row in (
                await session.execute(
                    select(
                        ConversationModel.id,
                        ConversationModel.custom_attributes,
                        ConversationModel.updated_at,
                    )
                )
            ).all()
        }
        user_type_id = (await session.execute(select(UserModel.user_type_id).limit(1))).scalar_one()

        built.group = UserGroupModel(id=uuid4(), name=f"backfillattr-{uuid4().hex[:8]}", is_deleted=0)
        session.add(built.group)
        suffix = uuid4().hex[:12]
        built.user = UserModel(
            id=uuid4(),
            username=f"backfillattr-{suffix}",
            email=f"backfillattr-{suffix}@example.test",
            hashed_password="x",
            user_type_id=user_type_id,
            is_active=1,
            group_id=built.group.id,
            is_deleted=0,
        )
        session.add(built.user)
        await session.flush()

        with acting_as(built.user.id):
            statistics = OperatorStatisticsModel(id=uuid4(), is_deleted=0)
            session.add(statistics)
            built.statistics_id = statistics.id
            operator = OperatorModel(
                id=uuid4(),
                first_name="Backfill",
                last_name="Attrs",
                statistics_id=statistics.id,
                is_active=1,
                user_id=built.user.id,
                is_deleted=0,
            )
            session.add(operator)
            built.operator_id = operator.id
            workflow = WorkflowModel(
                id=uuid4(),
                name=f"backfillattr-{suffix}",
                version="1",
                nodes=WORKFLOW_NODES,
                edges=[],
                user_id=built.user.id,
                is_deleted=0,
            )
            session.add(workflow)
            built.workflow_id = workflow.id
            agent = AgentModel(
                id=uuid4(),
                name=f"backfillattr-{suffix}",
                is_active=1,
                operator_id=operator.id,
                welcome_message="Welcome",
                workflow_id=workflow.id,
                is_deleted=0,
            )
            session.add(agent)
            built.agent_id = agent.id
            await session.flush()

            for attr_name, raw_response in (
                ("updated_conversation_id", RAW_RESPONSE_WITH_ATTRS),
                ("no_attrs_conversation_id", "{}"),
            ):
                conversation_id = uuid4()
                setattr(built, attr_name, conversation_id)
                session.add(
                    ConversationModel(
                        id=conversation_id,
                        operator_id=operator.id,
                        group_id=built.group.id,
                        conversation_type="chat",
                        conversation_date=SEEDED_UPDATED_AT,
                        status="finalized",
                        updated_at=SEEDED_UPDATED_AT,
                        is_deleted=0,
                    )
                )
                await session.flush()
                message_id = uuid4()
                built.message_ids.append(message_id)
                session.add(
                    TranscriptMessageModel(
                        id=message_id,
                        conversation_id=conversation_id,
                        start_time=0.0,
                        end_time=1.0,
                        speaker="agent",
                        text=f"backfillattr {attr_name}",
                        type="text",
                        sequence_number=1,
                        is_deleted=0,
                    )
                )
                await session.flush()
                session.add(
                    AgentResponseLogModel(
                        id=uuid4(),
                        transcript_message_id=message_id,
                        conversation_id=conversation_id,
                        raw_response=raw_response,
                        logged_at=SEEDED_UPDATED_AT,
                        is_deleted=0,
                    )
                )

            built.stale_conversation_id = uuid4()
            session.add(
                ConversationModel(
                    id=built.stale_conversation_id,
                    operator_id=operator.id,
                    group_id=built.group.id,
                    conversation_type="chat",
                    conversation_date=SEEDED_UPDATED_AT,
                    status="finalized",
                    custom_attributes={"stale": "seed"},
                    updated_at=SEEDED_UPDATED_AT,
                    is_deleted=0,
                )
            )
        await session.commit()

    try:
        yield built
    finally:
        conversation_ids = [
            built.updated_conversation_id,
            built.no_attrs_conversation_id,
            built.stale_conversation_id,
        ]
        async with maker() as session:
            await session.execute(
                delete(AgentResponseLogModel).where(AgentResponseLogModel.conversation_id.in_(conversation_ids))
            )
            await session.execute(
                delete(TranscriptMessageModel).where(TranscriptMessageModel.id.in_(built.message_ids))
            )
            await session.execute(delete(ConversationModel).where(ConversationModel.id.in_(conversation_ids)))
            await session.execute(delete(AgentModel).where(AgentModel.id == built.agent_id))
            await session.execute(delete(OperatorModel).where(OperatorModel.id == built.operator_id))
            await session.execute(
                delete(OperatorStatisticsModel).where(OperatorStatisticsModel.id == built.statistics_id)
            )
            await session.execute(delete(WorkflowModel).where(WorkflowModel.id == built.workflow_id))
            await session.execute(delete(UserModel).where(UserModel.id == built.user.id))
            await session.execute(delete(UserGroupModel).where(UserGroupModel.id == built.group.id))

            snapshot_ids = list(snapshot)
            for start in range(0, len(snapshot_ids), 5000):
                for conversation_id in snapshot_ids[start : start + 5000]:
                    attrs, stamp = snapshot[conversation_id]
                    await session.execute(
                        update(ConversationModel)
                        .where(ConversationModel.id == conversation_id)
                        .values(
                            custom_attributes=null() if attrs is None else attrs,
                            updated_at=stamp,
                        )
                    )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_incremental_backfill_preserves_updated_at(world):
    request_scope_factory = injector.get(RequestScopeFactory)
    with background_task_context():
        clear_tenant_context()
        async with request_scope_factory.create_scope():
            result = await backfill_custom_attributes_async()
    assert result["status"] == "completed"

    async with world.maker() as session:
        rows = (
            await session.execute(
                select(
                    ConversationModel.id,
                    ConversationModel.custom_attributes,
                    ConversationModel.updated_at,
                ).where(ConversationModel.id.in_([world.updated_conversation_id, world.no_attrs_conversation_id]))
            )
        ).all()
    by_id = {row.id: row for row in rows}
    assert set(by_id) == {world.updated_conversation_id, world.no_attrs_conversation_id}

    written = by_id[world.updated_conversation_id]
    assert written.custom_attributes == {"customer_tier": "gold"}
    assert written.updated_at == SEEDED_UPDATED_AT

    untouched = by_id[world.no_attrs_conversation_id]
    assert untouched.custom_attributes is None
    assert untouched.updated_at == SEEDED_UPDATED_AT


@pytest.mark.asyncio(loop_scope="module")
async def test_force_backfill_preserves_updated_at_across_all_branches(world):
    request_scope_factory = injector.get(RequestScopeFactory)
    with background_task_context():
        clear_tenant_context()
        async with request_scope_factory.create_scope():
            result = await backfill_custom_attributes_async(force=True)
    assert result["status"] == "completed"

    expected_ids = {
        world.updated_conversation_id,
        world.no_attrs_conversation_id,
        world.stale_conversation_id,
    }
    async with world.maker() as session:
        rows = (
            await session.execute(
                select(
                    ConversationModel.id,
                    ConversationModel.custom_attributes,
                    ConversationModel.updated_at,
                ).where(ConversationModel.id.in_(expected_ids))
            )
        ).all()
    by_id = {row.id: row for row in rows}
    assert set(by_id) == expected_ids

    rewritten = by_id[world.updated_conversation_id]
    assert rewritten.custom_attributes == {"customer_tier": "gold"}
    assert rewritten.updated_at == SEEDED_UPDATED_AT

    cleared = by_id[world.no_attrs_conversation_id]
    assert cleared.custom_attributes is None
    assert cleared.updated_at == SEEDED_UPDATED_AT

    stale = by_id[world.stale_conversation_id]
    assert stale.custom_attributes is None
    assert stale.updated_at == SEEDED_UPDATED_AT
