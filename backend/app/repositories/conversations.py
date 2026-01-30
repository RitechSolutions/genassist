import datetime
from typing import List, Optional, Tuple
from uuid import UUID
from injector import inject
from sqlalchemy import asc, desc, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.sentiment_enum import Sentiment
from app.core.utils.sql_alchemy_utils import add_dynamic_ordering, add_pagination
from app.db.models.conversation import ConversationModel
from app.db.models.message_model import TranscriptMessageModel
from app.schemas.conversation import ConversationCreate
from app.schemas.filter import ConversationFilter
from app.core.utils.bi_utils import filter_conversation_date, filter_conversation_messages_create_time
from app.db.models.conversation import ConversationAnalysisModel
from app.db.models.operator import OperatorModel
from app.db.models import AgentModel


@inject
class ConversationRepository:

    def __init__(self, db: AsyncSession):  # Auto-inject db
        self.db = db

    async def save_conversation(self, conversation_data: ConversationCreate):
        new_conversation = ConversationModel(
            **conversation_data.model_dump()
        )
        self.db.add(new_conversation)
        await self.db.commit()
        await self.db.refresh(new_conversation)
        return new_conversation

    async def fetch_conversation_by_id(
            self,
            conversation_id: UUID,
            include_messages: bool = False,
    ) -> Optional[ConversationModel]:
        """
        Fetch conversation by ID with optional message loading

        Args:
            conversation_id: The conversation UUID
            include_messages: Whether to eager load messages
        """
        query = select(ConversationModel).where(
            ConversationModel.id == conversation_id)

        if include_messages:
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback)
            )

        result = await self.db.execute(query)
        return result.scalars().first()

    async def fetch_conversation_by_id_full(
            self,
            conversation_id: UUID,
            conversation_filter: Optional[ConversationFilter] = None,
    ) -> Optional[ConversationModel]:
        """
        Fetch conversation with all related data (messages, feedback, recording, analysis)
        """
        # Build base query
        query = select(ConversationModel).where(ConversationModel.id == conversation_id).options(
            joinedload(ConversationModel.analysis),
            joinedload(ConversationModel.recording),
            joinedload(ConversationModel.operator),
        )

        # Build message loading with optional filtering
        if conversation_filter and (conversation_filter.from_create_datetime_messages or
                                    conversation_filter.to_create_datetime_messages):
            # Create filtered selectinload using .and_()
            message_filters = []
            if conversation_filter.from_create_datetime_messages:
                message_filters.append(
                    TranscriptMessageModel.create_time >= conversation_filter.from_create_datetime_messages
                )
            if conversation_filter.to_create_datetime_messages:
                message_filters.append(
                    TranscriptMessageModel.create_time <= conversation_filter.to_create_datetime_messages
                )

            query = query.options(
                selectinload(ConversationModel.messages.and_(*message_filters))
                .selectinload(TranscriptMessageModel.feedback)
            )
        else:
            # Load all messages
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback)
            )

        result = await self.db.execute(query)
        return result.scalars().first()

    async def fetch_conversations_by_customer_id(
            self,
            customer_id: UUID,
            include_messages: bool = False
    ) -> List[ConversationModel]:
        """
        Fetch all conversations in a thread, optionally with messages
        """
        query = select(ConversationModel).where(
            ConversationModel.customer_id == customer_id
        ).order_by(ConversationModel.updated_at.desc())

        if include_messages:
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback)
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_conversation_for_operator(
            self,
            operator_id: UUID,
            include_messages: bool = False
    ) -> Optional[ConversationModel]:
        """
        Get the most recent conversation for an operator
        """
        query = (
            select(ConversationModel)
            .where(ConversationModel.operator_id == operator_id)
            .order_by(ConversationModel.created_at.desc())
            .limit(1)
        )

        if include_messages:
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback)
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

    async def fetch_conversations_with_relations(
            self,
            conversation_filter: ConversationFilter,
            include_messages: bool = True,
    ) -> List[ConversationModel]:
        """
        Fetch conversations with recording and optional messages

        Note: include_messages=True may impact performance for large result sets.
        """
        query = (
            select(ConversationModel)
            .options(joinedload(ConversationModel.recording))
        )

        # Apply existing filters (from your current implementation)
        if conversation_filter.minimum_hostility_score:
            query = query.where(
                ConversationModel.in_progress_hostility_score >= conversation_filter.minimum_hostility_score
            )

        if conversation_filter.conversation_status:
            query = query.where(
                ConversationModel.status.in_(
                    [status.value for status in conversation_filter.conversation_status])
            )

        query = filter_conversation_date(conversation_filter, query)

        if conversation_filter.operator_id:
            query = query.where(ConversationModel.operator_id ==
                                conversation_filter.operator_id)

        if conversation_filter.customer_id:
            query = query.where(ConversationModel.customer_id ==
                                conversation_filter.customer_id)

        # filter based on sentiment score
        if conversation_filter.sentiment:
            if (conversation_filter.hostility_positive_max is None or
                    conversation_filter.hostility_neutral_max is None):
                raise AppException(error_key=ErrorKey.REQUIRED_INTERVAL_VALUES)
            query = (
                query.outerjoin(ConversationModel.analysis)
                .options(contains_eager(ConversationModel.analysis))
                .where(self._sentiment_predicate(conversation_filter))
            )
        else:
            query = query.options(selectinload(ConversationModel.analysis))

        # Conditional topic filtering: finalized status checks analysis, others check model
        if conversation_filter.conversation_topics:
            # Build topic filtering condition based on status
            topic_condition = or_(
                # For finalized conversations: check topic in conversationanalysis
                and_(
                    ConversationModel.status == ConversationStatus.FINALIZED.value,
                    ConversationModel.analysis.has(
                        ConversationAnalysisModel.topic.in_(
                            [topic.value for topic in conversation_filter.conversation_topics])
                    )
                ),
                # For all other conversations: check topic in conversationmodel
                and_(
                    ConversationModel.status != ConversationStatus.FINALIZED.value,
                    ConversationModel.topic.in_(
                        [topic.value for topic in conversation_filter.conversation_topics])
                )
            )

            query = query.where(topic_condition)

        if include_messages:
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback)
            )
            query = filter_conversation_messages_create_time(
                conversation_filter, query)
        else:
            # Just load analysis for sentiment/topic info
            query = query.options(selectinload(ConversationModel.analysis))

        # ——— dynamic ordering ———
        query = add_dynamic_ordering(ConversationModel, conversation_filter, query)

        # Pagination
        query = add_pagination(conversation_filter, query)

        result = await self.db.execute(query)
        return result.scalars().all()


    @staticmethod
    def _sentiment_predicate(filter: ConversationFilter):
        """Return a SQLAlchemy boolean expression that is TRUE when the
        conversation should be treated as `filter.sentiment` sentiment. There are two paths either in progress
        conversation where its decided based on some intervals where in_progress_hostility_score falls,
        or if the conversation has been finalized we check the scores of its analysis."""

        cm = ConversationModel
        ca = ConversationAnalysisModel  # shorthand

        # ── finalized branch ────────────────────────────────────────────
        pos_final = (ca.positive_sentiment > ca.negative_sentiment) & \
                    (ca.positive_sentiment > ca.neutral_sentiment)

        neg_final = (ca.negative_sentiment > ca.positive_sentiment) & \
                    (ca.negative_sentiment > ca.neutral_sentiment)

        neu_final = (ca.neutral_sentiment >= ca.positive_sentiment) & \
                    (ca.neutral_sentiment >= ca.negative_sentiment)

        # ── in-progress branch (score-based) ───────────────────────────
        positive_progress = cm.in_progress_hostility_score <= filter.hostility_positive_max
        neutral_progress = (cm.in_progress_hostility_score > filter.hostility_positive_max) & \
            (cm.in_progress_hostility_score <= filter.hostility_neutral_max)
        negative_progress = cm.in_progress_hostility_score > filter.hostility_neutral_max

        if filter.sentiment is Sentiment.POSITIVE:
            finalized_clause = pos_final
            in_progress_clause = positive_progress
        elif filter.sentiment is Sentiment.NEGATIVE:
            finalized_clause = neg_final
            in_progress_clause = negative_progress
        else:  # Sentiment.NEUTRAL
            finalized_clause = neu_final
            in_progress_clause = neutral_progress

        return or_(
            and_(cm.status == ConversationStatus.FINALIZED.value, finalized_clause),
            and_(cm.status != ConversationStatus.FINALIZED.value, in_progress_clause)
        )

    async def count_conversations(
            self, conversation_filter: ConversationFilter
    ) -> int:
        """
        Return the number of conversations whose status matches the
        values provided in `conversation_filter.conversation_status`.
        If no statuses are supplied, it simply returns the total row count.
        """
        query = select(func.count(ConversationModel.id))

        if conversation_filter.conversation_status:
            query = query.where(
                ConversationModel.status.in_(
                    [status.value for status in conversation_filter.conversation_status]
                )
            )

        result = await self.db.execute(query)
        return result.scalar_one()

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
        topic_bucket = func.initcap(
            func.trim(ConversationAnalysisModel.topic)).label("topic")

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
        q = select(ConversationModel).where(
            ConversationModel.zendesk_ticket_id == ticket_id)
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
            select(ConversationModel).where(
                ConversationModel.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def fetch_conversation_by_id_with_operator_agent(
        self, conversation_id: UUID
    ) -> Optional[ConversationModel]:
        """
        Fetch conversation by ID with operator and agent eager-loaded.
        Use this when you need to access conversation.operator.agent without triggering
        async lazy load (which would cause MissingGreenlet).
        """
        query = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .options(
                joinedload(ConversationModel.operator)
                .joinedload(OperatorModel.agent)
                .joinedload(AgentModel.security_settings)
            )
        )
        result = await self.db.execute(query)
        return result.unique().scalars().first()
