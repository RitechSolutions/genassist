"""Unit tests for the conversation topic options served from the analysts' topic lists"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.routes.conversations import router
from app.services.llm_analysts import LlmAnalystService


def _service(*analysts):
    repo = MagicMock(get_all=AsyncMock(return_value=list(analysts)))
    return LlmAnalystService(repo, MagicMock())


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
        "topics": [
            {"name": "Refund", "subtopics": ["Wrong plate", "Duplicate"]},
            {"name": "Other", "subtopics": []},
            {"name": "Product Inquiry", "subtopics": []},
            {"name": "Technical Support", "subtopics": []},
            {"name": "Billing Questions", "subtopics": []},
        ]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("analyst", [_analyst(["Refund"], is_active=0), SimpleNamespace(settings=None, is_active=1)])
async def test_no_active_topic_list_falls_back_to_the_default_topics(analyst):
    options = await _service(analyst).get_topic_options()
    assert [t.name for t in options.topics] == ["Product Inquiry", "Technical Support", "Billing Questions", "Other"]


@pytest.mark.asyncio
async def test_defaults_follow_the_configured_topics_keeping_the_configured_spelling():
    options = await _service(_analyst(["billing questions > Invoices", "Refund"])).get_topic_options()
    assert options.model_dump() == {
        "topics": [
            {"name": "billing questions", "subtopics": ["Invoices"]},
            {"name": "Refund", "subtopics": []},
            {"name": "Product Inquiry", "subtopics": []},
            {"name": "Technical Support", "subtopics": []},
            {"name": "Other", "subtopics": []},
        ]
    }


def test_topic_options_route_is_declared_before_the_conversation_id_route():
    paths = [route.path for route in router.routes if "GET" in getattr(route, "methods", ())]
    assert paths.index("/topic-options") < paths.index("/{conversation_id}")
