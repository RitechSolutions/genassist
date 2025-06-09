import datetime
from typing import List, Optional, Tuple
from uuid import UUID
from fastapi import Depends
from sqlalchemy import case, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.db.models.conversation import ConversationModel
from app.db.session import get_db
from app.schemas.conversation import ConversationCreate
from app.schemas.filter import ConversationFilter
from app.core.utils.bi_utils import filter_conversation_date
from app.db.models.conversation import ConversationAnalysisModel


class ConversationRepository:

    def __init__(self, db: AsyncSession = Depends(get_db)):  # Auto-inject db
        self.db = db

    async def save_conversation(self, conversation_data: ConversationCreate):
        new_conversation = ConversationModel(
            **conversation_data.model_dump()
        )
        self.db.add(new_conversation)
        await self.db.commit()
        await self.db.refresh(new_conversation)
        return new_conversation

    async def fetch_conversation_by_id(self, conversation_id: UUID) -> Optional[ConversationModel]:
         query = select(ConversationModel).where(ConversationModel.id == conversation_id)
         result = await self.db.execute(query)
         return result.scalars().first()

    async def fetch_conversation_by_id_full(self, conversation_id: UUID) -> Optional[ConversationModel]:
         query = select(ConversationModel).where(ConversationModel.id == conversation_id).options(
                 joinedload(ConversationModel.analysis),
                 joinedload(ConversationModel.recording),
                 )
         result = await self.db.execute(query)
         return result.scalars().first()


    async def get_latest_conversation_for_operator(self, operator_id: UUID) -> Optional[ConversationModel]:
        query = (
            select(ConversationModel)
            .where(ConversationModel.operator_id == operator_id)
            .order_by(ConversationModel.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_latest_conversation_with_analysis_for_operator(self, operator_id: UUID) -> Optional[ConversationModel]:
        query = (
            select(ConversationModel)
            .options(
                    joinedload(ConversationModel.analysis),
                    joinedload(ConversationModel.recording)  # ← Load recording too
                    )
            .where(ConversationModel.operator_id == operator_id)
            .order_by(ConversationModel.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def update_conversation(self, conversation: ConversationModel) -> ConversationModel:
        """
        Updates an existing conversation in DB
        """
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation


    async def fetch_conversations_with_recording(self, conversation_filter: ConversationFilter) -> list[ConversationModel]:
        query = (
            select(ConversationModel)
            .options(
                    joinedload(ConversationModel.analysis),
                    joinedload(ConversationModel.recording)
                    )
        )
        if conversation_filter.minimum_hostility_score:
            query = query.where(ConversationModel.in_progress_hostility_score >= conversation_filter.minimum_hostility_score)
        if conversation_filter.conversation_status:
            query = query.where(ConversationModel.status == conversation_filter.conversation_status)
        query = filter_conversation_date(conversation_filter, query)
        if conversation_filter.operator_id:
            query = query.where(ConversationModel.operator_id == conversation_filter.operator_id)

        # Pagination
        query = query.offset(conversation_filter.skip).limit(conversation_filter.limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_stale_conversations(self, cutoff_time: datetime):
        query = select(ConversationModel).where(
            ConversationModel.status == ConversationStatus.IN_PROGRESS.value,
            ConversationModel.updated_at < cutoff_time
        )
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def delete_conversation(self, conversation: ConversationModel):
        await self.db.delete(conversation)
        await self.db.commit()

    async def get_topics_count(self) -> List[Tuple[str, int]]:
        """
        Count *all* conversations, bucketed by analysis.topic (or 'Other' if none/mismatched).
        """
        topic_bucket = func.initcap(func.trim(ConversationAnalysisModel.topic)).label("topic")

        stmt = (
            select(
                topic_bucket,
                func.count(ConversationModel.id).label("count")
            )
            .select_from(ConversationModel)
            .outerjoin(
                ConversationAnalysisModel,
                ConversationAnalysisModel.conversation_id == ConversationModel.id
            )
            .group_by(topic_bucket)
        )

        result = await self.db.execute(stmt)
        return result.all()
    
    async def get_by_zendesk_ticket_id(self, ticket_id: int) -> Optional[ConversationModel]:
        q = select(ConversationModel).where(ConversationModel.zendesk_ticket_id == ticket_id)
        result = await self.db.execute(q)
        return result.scalars().first()
    
    async def set_zendesk_ticket_id(self, conversation_id: UUID, zendesk_ticket_id: int):
        conv = await self.get_by_id(conversation_id)
        if not conv:
            return None
        conv.zendesk_ticket_id = zendesk_ticket_id
        await self.db.commit()
        await self.db.refresh(conv)
        return conv
    
    async def get_by_id(self, conversation_id: UUID) -> Optional[ConversationModel]:
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        return result.scalar_one_or_none()