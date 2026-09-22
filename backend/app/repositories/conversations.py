import datetime
from typing import List, Optional, Sequence, Tuple
from uuid import UUID

from injector import inject
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models import AgentModel
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.db.models.message_model import TranscriptMessageModel
from app.db.models.operator import OperatorModel
from app.db.models.user import UserModel
from app.repositories.db_repository import DbRepository
from app.schemas.conversation import ConversationCreate
from app.schemas.filter import ConversationFilter


@inject
class ConversationRepository(DbRepository[ConversationModel]):

    def __init__(self, db: AsyncSession):  # Auto-inject db
        super().__init__(ConversationModel, db)

    async def resolve_group_id_for_operator(self, operator_id: UUID) -> Optional[UUID]:
        """User group for an agent's operator (console user), else agent creator's group."""
        from app.db.models.operator import OperatorModel

        stmt = (
            select(UserModel.group_id)
            .select_from(OperatorModel)
            .join(UserModel, UserModel.id == OperatorModel.user_id)
            .where(OperatorModel.id == operator_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        operator_group = result.scalar_one_or_none()
        if operator_group is not None:
            return operator_group

        stmt = (
            select(UserModel.group_id)
            .select_from(AgentModel)
            .join(UserModel, UserModel.id == AgentModel.created_by)
            .where(AgentModel.operator_id == operator_id)
            .limit(1)
            .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_conversation(self, conversation_data: ConversationCreate):
        data = conversation_data.model_dump()
        if data.get("group_id") is None:
            data["group_id"] = await self.resolve_group_id_for_operator(conversation_data.operator_id)
        new_conversation = ConversationModel(**data)
        self.db.add(new_conversation)
        await self.db.flush()
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
        query = select(ConversationModel).where(ConversationModel.id == conversation_id)

        if include_messages:
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback
                )
            )

        # Point lookup by primary key: group-scope row filtering is meant for
        # list/analytics queries, not for operating on a specific known
        # conversation (already gated by conversation-scoped auth/permissions).
        query = query.execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})

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
        query = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .options(
                joinedload(ConversationModel.analysis),
                joinedload(ConversationModel.recording),
                joinedload(ConversationModel.operator).joinedload(OperatorModel.agent),
                joinedload(ConversationModel.supervisor),
            )
        )

        # Build message loading with optional filtering
        if conversation_filter and (
            conversation_filter.from_create_datetime_messages
            or conversation_filter.to_create_datetime_messages
        ):
            # Create filtered selectinload using .and_()
            message_filters = []
            if conversation_filter.from_create_datetime_messages:
                message_filters.append(
                    TranscriptMessageModel.create_time
                    >= conversation_filter.from_create_datetime_messages
                )
            if conversation_filter.to_create_datetime_messages:
                message_filters.append(
                    TranscriptMessageModel.create_time
                    <= conversation_filter.to_create_datetime_messages
                )

            query = query.options(
                selectinload(
                    ConversationModel.messages.and_(*message_filters)
                ).selectinload(TranscriptMessageModel.feedback)
            )
        else:
            # Load all messages
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback
                )
            )

        # Point lookup by primary key: bypass group-scope row filtering (see
        # fetch_conversation_by_id).
        query = query.execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})

        result = await self.db.execute(query)
        return result.scalars().first()

    async def fetch_conversations_by_customer_id(
        self, customer_id: UUID, include_messages: bool = False
    ) -> List[ConversationModel]:
        """
        Fetch all conversations in a thread, optionally with messages
        """
        query = (
            select(ConversationModel)
            .where(ConversationModel.customer_id == customer_id)
            .order_by(ConversationModel.updated_at.desc())
        )

        if include_messages:
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback
                )
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_conversation_for_operator(
        self, operator_id: UUID, include_messages: bool = False
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
                    TranscriptMessageModel.feedback
                )
            )

        result = await self.db.execute(query)
        return result.scalars().first()

    async def update_conversation(
        self, conversation: ConversationModel
    ) -> ConversationModel:
        """
        Updates an existing conversation in DB
        """
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def update_custom_attributes(
        self, conversation_id: UUID, custom_attributes: dict
    ) -> None:
        """Update only the custom_attributes column without touching ORM relationships."""
        stmt = (
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(custom_attributes=custom_attributes)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def get_stale_conversations(
        self, cutoff_time: datetime.datetime
    ) -> Sequence[ConversationModel]:
        # add a limit to the query to prevent too many conversations from being returned
        limit = 100

        query = (
            select(ConversationModel)
            .options(selectinload(ConversationModel.messages))
            .where(
                ConversationModel.status == ConversationStatus.IN_PROGRESS.value,
                ConversationModel.updated_at < cutoff_time,
            )
        ).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def delete_conversation(self, conversation: ConversationModel):
        await self.db.delete(conversation)
        await self.db.flush()

    async def get_topics_count(self) -> List[Tuple[str, int]]:
        """
        Count *all* conversations, bucketed by analysis.topic (or 'Other' if none/mismatched).
        """
        topic_bucket = func.initcap(func.trim(ConversationAnalysisModel.topic)).label(
            "topic"
        )

        stmt = (
            select(topic_bucket, func.count(ConversationModel.id).label("count"))
            .select_from(ConversationModel)
            .outerjoin(
                ConversationAnalysisModel,
                ConversationAnalysisModel.conversation_id == ConversationModel.id,
            )
            .group_by(topic_bucket)
        )

        result = await self.db.execute(stmt)
        return result.all()

    async def get_by_zendesk_ticket_id(
        self, ticket_id: int
    ) -> Optional[ConversationModel]:
        q = select(ConversationModel).where(
            ConversationModel.zendesk_ticket_id == ticket_id
        )
        result = await self.db.execute(q)
        return result.scalars().first()

    async def set_zendesk_ticket_id(
        self, conversation_id: UUID, zendesk_ticket_id: int
    ):
        conv = await self.get_by_id(conversation_id)
        if not conv:
            return None
        conv.zendesk_ticket_id = zendesk_ticket_id
        await self.db.flush()
        await self.db.refresh(conv)
        return conv

    async def get_by_id(self, conversation_id: UUID) -> Optional[ConversationModel]:
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
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
            # Point lookup used for auth/agent resolution: bypass group-scope row
            # filtering so it also skips the joined AgentModel loader criteria.
            .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        )
        result = await self.db.execute(query)
        return result.unique().scalars().first()

    async def fetch_conversations_by_ids(
        self,
        conversation_ids: List[UUID],
        include_messages: bool = False,
    ) -> List[ConversationModel]:
        """Fetch multiple conversations by ID in a single query."""
        query = select(ConversationModel).where(ConversationModel.id.in_(conversation_ids))
        if include_messages:
            query = query.options(
                selectinload(ConversationModel.messages)
            )
        result = await self.db.execute(query)
        return list(result.unique().scalars().all())

    async def get_finalized_without_analysis(self, limit: int = 100) -> Sequence[ConversationModel]:
        """Return finalized conversations that have no conversation_analysis row."""
        query = (
            select(ConversationModel)
            .outerjoin(
                ConversationAnalysisModel,
                ConversationAnalysisModel.conversation_id == ConversationModel.id,
            )
            .where(
                ConversationModel.status == ConversationStatus.FINALIZED.value,
                ConversationAnalysisModel.id.is_(None),
            )
            .limit(limit)
        )
        result = await self.db.execute(query)
        return result.scalars().all()
