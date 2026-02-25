from fastapi import Depends
from uuid import UUID
from typing import Optional

from fastapi_injector import Injected
from injector import inject

from app.repositories.conversation_analysis import ConversationAnalysisRepository
from app.schemas.conversation_analysis import AnalysisResult, ConversationAnalysisCreate


def _truncate(text: Optional[str], max_length: int = 255) -> str:
    if not text:
        return ""
    return text[:max_length]


@inject
class ConversationAnalysisService:
    def __init__(self, repository: ConversationAnalysisRepository):
        self.repository = repository

    async def save_conversation_analysis(self, conversation: ConversationAnalysisCreate):
        model = await self.repository.save_conversation_analysis(conversation)
        return model

    async def create_conversation_analysis(
        self,
        gpt_analysis: AnalysisResult,
        llm_analyst_id: UUID,
        conversation_id: UUID,
    ):
        # Ensure we never exceed VARCHAR(255) limits in the DB
        topic = _truncate(getattr(gpt_analysis, "title", None))
        summary = _truncate(getattr(gpt_analysis, "summary", None))
        tone = _truncate(gpt_analysis.kpi_metrics.get("Tone", ""))

        conversation_analysis_create = ConversationAnalysisCreate(
            conversation_id=conversation_id,
            topic=topic,
            summary=summary,
            customer_satisfaction=gpt_analysis.kpi_metrics.get(
                "Customer Satisfaction", 0
            ),
            operator_knowledge=gpt_analysis.kpi_metrics.get("Operator Knowledge", 0),
            resolution_rate=gpt_analysis.kpi_metrics.get("Resolution Rate", 0),
            positive_sentiment=gpt_analysis.kpi_metrics.get(
                "Sentiment", {}
            ).get("positive", 0),
            neutral_sentiment=gpt_analysis.kpi_metrics.get(
                "Sentiment", {}
            ).get("neutral", 0),
            negative_sentiment=gpt_analysis.kpi_metrics.get(
                "Sentiment", {}
            ).get("negative", 0),
            tone=tone,
            llm_analyst_id=llm_analyst_id,
            efficiency=gpt_analysis.kpi_metrics.get("Efficiency", 0),
            response_time=gpt_analysis.kpi_metrics.get("Response Time", 0),
            quality_of_service=gpt_analysis.kpi_metrics.get("Quality of Service", 0),
        )
        return await self.save_conversation_analysis(conversation_analysis_create)