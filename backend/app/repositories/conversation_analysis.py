from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.db.models.conversation import ConversationAnalysisModel
from app.schemas.conversation_analysis import ConversationAnalysisCreate

@inject
class ConversationAnalysisRepository:

    def __init__(self, db: AsyncSession):  # Auto-inject db
        self.db = db

    async def save_conversation_analysis(self, analysis_data: ConversationAnalysisCreate) -> ConversationAnalysisModel:
        new_analysis = ConversationAnalysisModel(
                conversation_id=analysis_data.conversation_id,
                topic=analysis_data.topic,
                summary=analysis_data.summary,
                positive_sentiment=analysis_data.positive_sentiment,
                negative_sentiment=analysis_data.negative_sentiment,
                neutral_sentiment=analysis_data.neutral_sentiment,
                tone=analysis_data.tone,
                customer_satisfaction=analysis_data.customer_satisfaction,
                operator_knowledge=analysis_data.operator_knowledge,
                resolution_rate=analysis_data.resolution_rate,
                llm_analyst_id=analysis_data.llm_analyst_id,
                efficiency=analysis_data.efficiency,
                response_time=analysis_data.response_time,
                quality_of_service=analysis_data.quality_of_service,
                )
        self.db.add(new_analysis)
        await self.db.commit()
        await self.db.refresh(new_analysis)
        return new_analysis

    async def get_by_conversation_id(self, conversation_id: UUID) -> Optional[ConversationAnalysisModel]:
        query = select(ConversationAnalysisModel).where(ConversationAnalysisModel.conversation_id == conversation_id)
        result = await self.db.execute(query)
        return result.scalars().first()

