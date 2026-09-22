from typing import List

from injector import inject
from sqlalchemy import String, and_, asc, cast, desc, distinct, func, nulls_last, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.future import select
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.bi_utils import (
    filter_conversation_date,
    filter_conversation_messages_create_time,
)
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.sentiment_enum import Sentiment
from app.core.utils.enums.sort_direction_enum import SortDirection
from app.core.utils.sql_alchemy_utils import add_dynamic_ordering, add_pagination
from app.db.events.group_scope import get_group_scope_clause
from app.db.models import AgentModel
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.db.models.message_model import TranscriptMessageModel
from app.db.models.operator import OperatorModel
from app.db.session_types import ReadOnlySession
from app.schemas.filter import ConversationFilter

# KPI score fields on ConversationAnalysisModel (0-10 scale).
# Used for sorting, filtering, and join detection.
ANALYSIS_SCORE_FIELDS = frozenset({
    "customer_satisfaction",
    "quality_of_service",
    "resolution_rate",
    "efficiency",
})


@inject
class ConversationReadRepository:
    """Conversation list and count queries, served from the read replica when one is configured"""

    def __init__(self, db: ReadOnlySession):
        self.db = db

    def _get_conversation_group_clause(self):
        """Return a group-scope WHERE clause only when the current user has a group or
        supervised groups. No-group users fall back to the operator_id filter set by the
        service layer, so we must not apply the created_by==user_id fallback here."""
        try:
            group_id = context.get("group_id")
            supervised_group_ids = context.get("supervised_group_ids") or []
        except (LookupError, ContextDoesNotExistError):
            return None
        if not (group_id or supervised_group_ids):
            return None
        return get_group_scope_clause(ConversationModel)  # returns None

    def _apply_base_filters(self, query, conversation_filter: ConversationFilter):
        """Apply all shared WHERE clauses so fetch and count stay in sync."""
        if conversation_filter.minimum_hostility_score:
            query = query.where(
                ConversationModel.in_progress_hostility_score
                >= conversation_filter.minimum_hostility_score
            )

        if conversation_filter.conversation_status:
            query = query.where(
                ConversationModel.status.in_(
                    [status.value for status in conversation_filter.conversation_status]
                )
            )

        query = filter_conversation_date(conversation_filter, query)

        if conversation_filter.operator_id:
            query = query.where(
                ConversationModel.operator_id == conversation_filter.operator_id
            )

        if conversation_filter.customer_id:
            query = query.where(
                ConversationModel.customer_id == conversation_filter.customer_id
            )

        # Agent/Workflow filter: join Operator → Agent when either filter is active
        if conversation_filter.agent_id or conversation_filter.workflow_id:
            query = query.join(
                OperatorModel, ConversationModel.operator_id == OperatorModel.id
            ).join(
                AgentModel, AgentModel.operator_id == OperatorModel.id
            )
            if conversation_filter.agent_id:
                query = query.where(AgentModel.id == conversation_filter.agent_id)
            if conversation_filter.workflow_id:
                query = query.where(AgentModel.workflow_id == conversation_filter.workflow_id)

        if conversation_filter.exclude_empty:
            query = query.where(ConversationModel.word_count > 0)

        if conversation_filter.search:
            search_term = f"%{conversation_filter.search}%"
            # Relationship predicates keep their FROM when the outer query joins the same table.
            query = query.where(
                or_(
                    cast(ConversationModel.id, String).ilike(search_term),
                    ConversationModel.topic.ilike(search_term),
                    ConversationModel.analysis.has(
                        ConversationAnalysisModel.summary.ilike(search_term)
                    ),
                    self._message_text_matches(conversation_filter.search),
                )
            )

        if conversation_filter.email:
            email_normalized = conversation_filter.email.strip().lower()
            json_match = (
                ConversationModel.custom_attributes["pii"]["requester_email"].astext
                == email_normalized
            )
            query = query.where(
                or_(json_match, self._message_text_matches(email_normalized))
            )

        if conversation_filter.id_suffix:
            query = query.where(
                cast(ConversationModel.id, String).like(f"%{conversation_filter.id_suffix.lower()}%")
            )

        custom_attrs = conversation_filter.custom_attributes_dict
        if custom_attrs:
            # Use @> (contains) operator to leverage the GIN index
            query = query.where(
                ConversationModel.custom_attributes.op("@>")(
                    cast(custom_attrs, JSONB)
                )
            )

        # Conditional topic filtering
        if conversation_filter.conversation_topics:
            topic_condition = or_(
                and_(
                    ConversationModel.status == ConversationStatus.FINALIZED.value,
                    ConversationModel.analysis.has(
                        ConversationAnalysisModel.topic.in_(
                            [
                                topic.value
                                for topic in conversation_filter.conversation_topics
                            ]
                        )
                    ),
                ),
                and_(
                    ConversationModel.status != ConversationStatus.FINALIZED.value,
                    ConversationModel.topic.in_(
                        [
                            topic.value
                            for topic in conversation_filter.conversation_topics
                        ]
                    ),
                ),
            )
            query = query.where(topic_condition)

        return query

    @staticmethod
    def _message_text_matches(text: str):
        """EXISTS on the conversation's messages via full-text search."""
        ts_query = func.plainto_tsquery("english", text)
        return ConversationModel.messages.any(
            TranscriptMessageModel.text_search.op("@@")(ts_query)
        )

    def _needs_analysis_join(self, conversation_filter: ConversationFilter) -> bool:
        """Return True when we must outerjoin ConversationAnalysisModel."""
        if conversation_filter.sentiment:
            return True
        if (
            conversation_filter.order_by
            and conversation_filter.order_by.value in ANALYSIS_SCORE_FIELDS
        ):
            return True
        # Score range filters
        for field in ANALYSIS_SCORE_FIELDS:
            for attr in (f"{field}_min", f"{field}_max"):
                if getattr(conversation_filter, attr, None) is not None:
                    return True
        return False

    def _apply_score_range_filters(self, query, conversation_filter: ConversationFilter):
        """Apply WHERE clauses for AI insight score range filters."""
        for name in ANALYSIS_SCORE_FIELDS:
            col = getattr(ConversationAnalysisModel, name)
            min_val = getattr(conversation_filter, f"{name}_min", None)
            max_val = getattr(conversation_filter, f"{name}_max", None)
            if min_val is not None:
                query = query.where(col >= min_val)
            if max_val is not None:
                query = query.where(col <= max_val)
        return query

    async def fetch_conversations_with_relations(
        self,
        conversation_filter: ConversationFilter,
        include_messages: bool = True,
    ) -> List[ConversationModel]:
        """
        Fetch conversations with recording and optional messages

        Note: include_messages=True may impact performance for large result sets.
        """
        query = select(ConversationModel).options(
            joinedload(ConversationModel.recording),
            joinedload(ConversationModel.supervisor),
            selectinload(ConversationModel.operator).selectinload(OperatorModel.agent),
        )

        query = self._apply_base_filters(query, conversation_filter)

        # Determine analysis join strategy once
        needs_join = self._needs_analysis_join(conversation_filter)

        if needs_join:
            if conversation_filter.sentiment and (
                conversation_filter.hostility_positive_max is None
                or conversation_filter.hostility_neutral_max is None
            ):
                raise AppException(error_key=ErrorKey.REQUIRED_INTERVAL_VALUES)

            query = (
                query.outerjoin(ConversationModel.analysis)
                .options(contains_eager(ConversationModel.analysis))
            )
            if conversation_filter.sentiment:
                query = query.where(self._sentiment_predicate(conversation_filter))
            query = self._apply_score_range_filters(query, conversation_filter)
        else:
            query = query.options(selectinload(ConversationModel.analysis))

        if include_messages:
            query = query.options(
                selectinload(ConversationModel.messages).selectinload(
                    TranscriptMessageModel.feedback
                )
            )
            query = filter_conversation_messages_create_time(conversation_filter, query)
        # ——— dynamic ordering ———
        if (
            conversation_filter.order_by
            and conversation_filter.order_by.value in ANALYSIS_SCORE_FIELDS
        ):
            col = getattr(ConversationAnalysisModel, conversation_filter.order_by.value)
            if conversation_filter.sort_direction == SortDirection.DESC:
                query = query.order_by(nulls_last(desc(col)))
            else:
                query = query.order_by(nulls_last(asc(col)))
        else:
            query = add_dynamic_ordering(ConversationModel, conversation_filter, query)

        # Pagination
        query = add_pagination(conversation_filter, query)

        result = await self.db.execute(query)
        # The analysis outerjoin (needs_join branch) can emit one row per
        # (conversation, analysis) pair when a conversation has more than one
        # analysis row, so collapse duplicate ConversationModel identities.
        return result.unique().scalars().all()

    @staticmethod
    def _sentiment_predicate(conversation_filter: ConversationFilter):
        """Return a SQLAlchemy boolean expression that is TRUE when the
        conversation should be treated as the requested sentiment. There are two paths:
        in-progress conversations where it's decided based on hostility score intervals,
        or finalized conversations where we check the analysis scores.
        """

        cm = ConversationModel
        ca = ConversationAnalysisModel

        # ── finalized branch ────────────────────────────────────────────
        pos_final = (ca.positive_sentiment > ca.negative_sentiment) & (
            ca.positive_sentiment > ca.neutral_sentiment
        )

        neg_final = (ca.negative_sentiment > ca.positive_sentiment) & (
            ca.negative_sentiment > ca.neutral_sentiment
        )

        neu_final = (ca.neutral_sentiment >= ca.positive_sentiment) & (
            ca.neutral_sentiment >= ca.negative_sentiment
        )

        # ── in-progress branch (score-based) ───────────────────────────
        positive_progress = (
            cm.in_progress_hostility_score <= conversation_filter.hostility_positive_max
        )
        neutral_progress = (
            cm.in_progress_hostility_score > conversation_filter.hostility_positive_max
        ) & (cm.in_progress_hostility_score <= conversation_filter.hostility_neutral_max)
        negative_progress = (
            cm.in_progress_hostility_score > conversation_filter.hostility_neutral_max
        )

        if conversation_filter.sentiment is Sentiment.POSITIVE:
            finalized_clause = pos_final
            in_progress_clause = positive_progress
        elif conversation_filter.sentiment is Sentiment.NEGATIVE:
            finalized_clause = neg_final
            in_progress_clause = negative_progress
        else:  # Sentiment.NEUTRAL
            finalized_clause = neu_final
            in_progress_clause = neutral_progress

        return or_(
            and_(cm.status == ConversationStatus.FINALIZED.value, finalized_clause),
            and_(cm.status != ConversationStatus.FINALIZED.value, in_progress_clause),
        )

    async def count_conversations(self, conversation_filter: ConversationFilter) -> int:
        """
        Return the total count of conversations matching ALL active filters.
        """
        # Count distinct conversations: the analysis outerjoin below can repeat
        # a conversation once per analysis row, which would inflate the total.
        query = select(func.count(distinct(ConversationModel.id)))
        query = self._apply_base_filters(query, conversation_filter)

        group_clause = self._get_conversation_group_clause()
        if group_clause is not None:
            query = query.where(group_clause)

        # Sentiment and score range filters need the analysis join
        needs_join = self._needs_analysis_join(conversation_filter)
        if needs_join:
            if conversation_filter.sentiment and (
                conversation_filter.hostility_positive_max is None
                or conversation_filter.hostility_neutral_max is None
            ):
                raise AppException(error_key=ErrorKey.REQUIRED_INTERVAL_VALUES)

            query = query.outerjoin(
                ConversationAnalysisModel,
                ConversationAnalysisModel.conversation_id == ConversationModel.id,
            )
            if conversation_filter.sentiment:
                query = query.where(self._sentiment_predicate(conversation_filter))
            query = self._apply_score_range_filters(query, conversation_filter)

        result = await self.db.execute(query)
        return result.scalar_one()
