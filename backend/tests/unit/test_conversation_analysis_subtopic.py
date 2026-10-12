"""Unit tests for storing the analysis sub-topic, without a database"""

from uuid import uuid4

import pytest

from app.schemas.conversation_analysis import AnalysisResult
from app.services.conversation_analysis import ConversationAnalysisService


class FakeRepo:
    async def save_conversation_analysis(self, analysis):
        return analysis


def _analysis(**kpi_metrics):
    return AnalysisResult(summary="s", title="Refund", kpi_metrics=kpi_metrics)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metrics, expected",
    [({"Subtopic": "Wrong plate"}, "Wrong plate"), ({}, None), ({"Subtopic": ""}, None), ({"Subtopic": "x" * 300}, "x" * 255)],
)
async def test_subtopic_is_mapped_from_the_verdict(metrics, expected):
    service = ConversationAnalysisService(FakeRepo())
    created = await service.create_conversation_analysis(_analysis(**metrics), uuid4(), uuid4())
    assert created.subtopic == expected
