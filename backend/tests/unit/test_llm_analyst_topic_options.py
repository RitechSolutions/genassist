"""Unit tests for the conversation topic options served from the analysts' topic lists"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.routes.conversations import router
from app.services.llm_analysts import LlmAnalystService


def _service(*analysts, stored=()):
    repo = MagicMock(get_all=AsyncMock(return_value=list(analysts)))
    analysis_repo = MagicMock(list_distinct_topics=AsyncMock(return_value=list(stored)))
    return LlmAnalystService(repo, MagicMock(), analysis_repo)


def _analyst(topics, is_active=1):
    return SimpleNamespace(settings={"topics": topics}, is_active=is_active)


@pytest.mark.asyncio
async def test_options_are_the_union_of_active_analysts():
    service = _service(
        _analyst(["Refund", "Refund > Wrong plate"]),
        _analyst(["refund > Duplicate", "Other"]),
        _analyst(["Inactive topic"], is_active=0),
        SimpleNamespace(settings=None, is_active=1),
    )
    options = await service.get_topic_options()
    assert options.model_dump() == {
        "topics": [{"name": "Refund", "subtopics": ["Wrong plate", "Duplicate"]}, {"name": "Other", "subtopics": []}]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("analyst", [_analyst(["Refund"], is_active=0), SimpleNamespace(settings=None, is_active=1)])
async def test_no_active_topic_list_falls_back_to_the_default_topics(analyst):
    options = await _service(analyst).get_topic_options()
    assert [t.name for t in options.topics] == ["Product Inquiry", "Technical Support", "Billing Questions", "Other"]


@pytest.mark.asyncio
async def test_stored_topics_follow_the_configured_ones_without_duplicates():
    service = _service(
        _analyst(["Refund", "Refund > Wrong plate"]),
        stored=[("Billing Questions", "Invoices"), ("Billing Questions", None), ("refund", "Duplicate"), ("Other", "")],
    )
    options = await service.get_topic_options()
    assert options.model_dump() == {
        "topics": [
            {"name": "Refund", "subtopics": ["Wrong plate", "Duplicate"]},
            {"name": "Billing Questions", "subtopics": ["Invoices"]},
            {"name": "Other", "subtopics": []},
        ]
    }


def test_topic_options_route_is_declared_before_the_conversation_id_route():
    paths = [route.path for route in router.routes if "GET" in getattr(route, "methods", ())]
    assert paths.index("/topic-options") < paths.index("/{conversation_id}")
