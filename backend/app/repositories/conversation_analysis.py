from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG, get_group_scope_clause
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.repositories.db_repository import DbRepository
from app.schemas.conversation_analysis import ConversationAnalysisCreate

@inject
class ConversationAnalysisRepository(DbRepository[ConversationAnalysisModel]):

    def __init__(self, db: AsyncSession):  # Auto-inject db
        super().__init__(ConversationAnalysisModel, db)

    async def save_conversation_analysis(self, analysis_data: ConversationAnalysisCreate) -> ConversationAnalysisModel:
        # Upsert by conversation_id: a conversation must have at most one analysis row.
        # Re-analysis (finalize/backfill races, Zendesk re-close, etc.) must REPLACE the
        # existing row in place rather than insert a duplicate.
        fields = dict(
                topic=analysis_data.topic,
                subtopic=analysis_data.subtopic,
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

        existing = await self.get_by_conversation_id(analysis_data.conversation_id)
        if existing is not None:
            # Update in place, preserving the same id (and any FK references to it).
            for key, value in fields.items():
                setattr(existing, key, value)
            analysis = existing
        else:
            analysis = ConversationAnalysisModel(
                    conversation_id=analysis_data.conversation_id,
                    **fields,
                    )
            self.db.add(analysis)

        await self.db.flush()
        await self.db.refresh(analysis)
        return analysis

    async def list_distinct_topics(self) -> list[tuple[str, Optional[str]]]:
        """Every (topic, subtopic) pair stored on a finalized conversation the caller can see, topics first"""
        query = (
            select(ConversationAnalysisModel.topic, ConversationAnalysisModel.subtopic)
            .where(ConversationAnalysisModel.topic.isnot(None), ConversationAnalysisModel.topic != "")
            .distinct()
            .order_by(ConversationAnalysisModel.topic, ConversationAnalysisModel.subtopic)
        )
        group_clause = get_group_scope_clause(ConversationModel)
        if group_clause is not None:
            query = (
                query.join(ConversationModel, ConversationModel.id == ConversationAnalysisModel.conversation_id)
                .where(group_clause)
                .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
            )
        return [(topic, subtopic) for topic, subtopic in (await self.db.execute(query)).all()]

    async def get_by_conversation_id(self, conversation_id: UUID) -> Optional[ConversationAnalysisModel]:
        query = select(ConversationAnalysisModel).where(ConversationAnalysisModel.conversation_id == conversation_id)
        result = await self.db.execute(query)
        return result.scalars().first()

