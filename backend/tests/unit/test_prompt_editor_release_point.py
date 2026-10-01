"""Release point with real AsyncSession. Routes return DB before model calls.
Needs real transactions and listeners (engine/repos mocked)"""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config.settings import settings
from app.core.exceptions.exception_classes import AppException
from app.schemas.prompt_editor import PromptEvalRequest, PromptOptimizeRequest
from app.services.prompt_editor import PromptEditorService

WORKFLOW_ID = uuid4()
NODE_ID = "n1"
FIELD = "systemPrompt"
SUITE_ID = uuid4()
AGENT_NODE = {"id": NODE_ID, "type": "agentNode", "data": {"name": "A"}}
PROVIDER = SimpleNamespace(id=uuid4(), llm_model_provider="openai", llm_model="gpt-4o")

SUGGESTION = json.dumps({"improved_prompt": "Be concise.", "explanation": "Tightened."})

_engine = create_async_engine(settings.DATABASE_URL)
_session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session():
    live = _session_maker()
    try:
        yield live
    finally:
        await live.close()


def _case():
    return SimpleNamespace(id=uuid4(), input_data={"message": "hi"}, expected_output={"value": "hi"})


def _service(db, cases):
    workflow_repo = AsyncMock()
    workflow_repo.get_access_row.return_value = SimpleNamespace(
        id=WORKFLOW_ID,
        agent_id=None,
        created_by=None,
        updated_at=datetime.now(timezone.utc),
        nodes=[AGENT_NODE],
        agent_visible=True,
    )
    config_repo = AsyncMock()
    config_repo.get_by_context.return_value = SimpleNamespace(gold_suite_id=SUITE_ID)
    case_repo = AsyncMock()
    case_repo.get_case_index_for_suite.return_value = [(case.id, None, None) for case in cases]
    case_repo.get_cases_by_ids.return_value = cases
    service = PromptEditorService(
        version_repo=AsyncMock(),
        config_repo=config_repo,
        suite_repo=AsyncMock(),
        case_repo=case_repo,
        workflow_repo=workflow_repo,
        db=db,
    )
    service._persist_usage = AsyncMock()
    return service


def _injector(llm, build_error=None):
    provider_service = SimpleNamespace(get_by_id=AsyncMock(return_value=PROVIDER))
    llm_provider = SimpleNamespace(
        get_model_from_provider=AsyncMock(side_effect=build_error)
        if build_error
        else AsyncMock(return_value=llm)
    )
    fake = MagicMock()
    fake.get.side_effect = lambda cls: (
        provider_service if cls.__name__ == "LlmProviderService" else llm_provider
    )
    return fake


def _watching_llm(db, seen, reply="hi"):
    llm = AsyncMock()

    async def invoke(_messages):
        seen.append(db.in_transaction())
        return AIMessage(content=reply)

    llm.ainvoke.side_effect = invoke
    return llm


def _eval_request():
    return PromptEvalRequest(
        prompt_content="You are helpful.", provider_id=PROVIDER.id, techniques=["exact_match"]
    )


def _optimize_request():
    return PromptOptimizeRequest(provider_id=PROVIDER.id, current_prompt="You are helpful.")


class TestReleasePoint:
    @pytest.mark.asyncio
    async def test_an_open_transaction_is_released_before_the_check_calls_the_model(self, session):
        await session.begin()
        seen = []
        service = _service(session, [_case()])

        with patch("app.dependencies.injector.injector", _injector(_watching_llm(session, seen))):
            await service.evaluate_prompt(WORKFLOW_ID, NODE_ID, FIELD, _eval_request())

        assert seen == [False]
        assert session.in_transaction() is False

    @pytest.mark.asyncio
    async def test_an_open_transaction_is_released_before_the_rewrite_calls_the_model(self, session):
        await session.begin()
        seen = []
        service = _service(session, [_case()])
        llm = _watching_llm(session, seen, reply=SUGGESTION)

        with patch("app.dependencies.injector.injector", _injector(llm)):
            await service.optimize_prompt(WORKFLOW_ID, NODE_ID, FIELD, _optimize_request())

        assert seen == [False]
        assert session.in_transaction() is False

    @pytest.mark.asyncio
    async def test_a_failed_build_releases_the_session_and_leaves_it_usable(self, session):
        await session.begin()
        service = _service(session, [_case()])
        injector = _injector(None, build_error=RuntimeError("missing package"))

        with pytest.raises(AppException) as exc_info:
            with patch("app.dependencies.injector.injector", injector):
                await service.evaluate_prompt(WORKFLOW_ID, NODE_ID, FIELD, _eval_request())

        assert exc_info.value.status_code == 502
        assert session.in_transaction() is False
        await session.begin()
        assert session.in_transaction() is True
        await session.rollback()
