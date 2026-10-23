from typing import Iterable, List, Optional
from uuid import UUID
from injector import inject
from sqlalchemy import and_, case, func, null, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import defer, selectinload

from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.issue_status_enum import DEFAULT_ISSUE_STATUS_KEY
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG, get_group_scope_clause
from app.db.models.agent import AgentModel
from app.db.models.audit_log import AuditLogModel
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.db.models.message_issue import MessageIssueModel, MessageIssueNoteModel
from app.db.models.message_model import MessageFeedbackModel, TranscriptMessageModel
from app.db.models.operator import OperatorModel
from app.db.models.user import UserModel
from app.db.models.workflow import WorkflowModel
from app.repositories.db_repository import DbRepository
from app.schemas.conversation_transcript import TranscriptSegmentFeedback
from app.schemas.filter import MessageIssueFilter, MessageIssueSummaryFilter


@inject
class TranscriptMessageRepository(DbRepository[TranscriptMessageModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(TranscriptMessageModel, db)


    async def save_messages(self, messages: List[TranscriptMessageModel]) -> List[TranscriptMessageModel]:
        """Save multiple transcript messages"""
        self.db.add_all(messages)
        await self.db.flush()
        for msg in messages:
            await self.db.refresh(msg)
        return messages


    async def get_latest_sequence_number(
            self,
            conversation_id: UUID
            ) -> int:
        """Get the latest sequence number for a conversation (returns -1 if no messages)"""
        from sqlalchemy import func

        query = select(func.max(TranscriptMessageModel.sequence_number)).where(
                TranscriptMessageModel.conversation_id == conversation_id
                )
        result = await self.db.execute(query)
        max_seq = result.scalar()

        # Return -1 if no messages exist, so next_sequence will be 0
        return max_seq if max_seq is not None else -1


    async def get_messages_by_conversation_id(
            self,
            conversation_id: UUID,
            ) -> List[TranscriptMessageModel]:
        """Get all messages for a conversation, ordered by sequence"""
        query = select(TranscriptMessageModel).where(
                TranscriptMessageModel.conversation_id == conversation_id
                ).order_by(TranscriptMessageModel.sequence_number)

        query = query.options(selectinload(TranscriptMessageModel.feedback))

        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def get_message_by_message_id(
            self,
            message_id: UUID,
            ) -> Optional[TranscriptMessageModel]:
        """Get a specific message by its message_id"""
        query = select(TranscriptMessageModel).where(
                TranscriptMessageModel.id == message_id
                )

        query = query.options(selectinload(TranscriptMessageModel.feedback))

        result = await self.db.execute(query)
        return result.scalars().first()


    async def add_message_feedback(
            self,
            message_id: UUID,
            transcript_feedback: TranscriptSegmentFeedback,
            ) -> tuple[MessageFeedbackModel, Optional[str]]:
        """Add feedback to a message. Returns the feedback model and the previous feedback value (or None if new)."""
        from datetime import timezone, datetime

        # Check if user already has feedback
        existing_feedback = await self.get_user_feedback_for_message(
                message_id,
                get_current_user_id()
                )

        if existing_feedback:
            # Capture old value before updating
            previous_feedback = existing_feedback.feedback
            # A comment-only update (feedback is None) must keep the existing rating;
            # a rating-only update (feedback_message is None) must keep the comment.
            if transcript_feedback.feedback is not None:
                existing_feedback.feedback = transcript_feedback.feedback.value
            if transcript_feedback.feedback_message is not None:
                existing_feedback.feedback_message = transcript_feedback.feedback_message
            existing_feedback.feedback_timestamp = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(existing_feedback)
            return existing_feedback, previous_feedback
        else:
            # Create new feedback. Comment-only (no rating) is stored with an empty
            # feedback value so it doesn't register as a thumbs up/down.
            new_feedback = MessageFeedbackModel(
                    message_id=message_id,
                    feedback=transcript_feedback.feedback.value
                    if transcript_feedback.feedback is not None
                    else "",
                    feedback_timestamp=datetime.now(timezone.utc),
                    feedback_user_id=get_current_user_id(),
                    feedback_message=transcript_feedback.feedback_message
                    )
            self.db.add(new_feedback)
            await self.db.flush()
            await self.db.refresh(new_feedback)
            return new_feedback, None


    async def get_user_feedback_for_message(
            self,
            message_id: UUID,
            user_id: UUID
            ) -> Optional[MessageFeedbackModel]:
        """Get a specific user's feedback for a message"""
        query = select(MessageFeedbackModel).where(
                MessageFeedbackModel.message_id == message_id,
                MessageFeedbackModel.feedback_user_id == user_id
                )
        result = await self.db.execute(query)
        return result.scalars().first()


    async def delete_messages_by_conversation_id(self, conversation_id: UUID):
        """Delete all messages for a conversation (cascade will handle feedback)"""
        messages = await self.get_messages_by_conversation_id(conversation_id)
        for message in messages:
            await self.db.delete(message)
        await self.db.flush()


    async def get_messages_by_type(
            self,
            conversation_id: UUID,
            message_type: str
            ) -> List[TranscriptMessageModel]:
        """Get messages filtered by type"""
        query = select(TranscriptMessageModel).where(
                TranscriptMessageModel.conversation_id == conversation_id,
                TranscriptMessageModel.type == message_type
                ).order_by(TranscriptMessageModel.sequence_number)

        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def get_latest_messages_by_types(
            self,
            conversation_id: UUID,
            message_types: Iterable[str],
            limit: int
            ) -> List[TranscriptMessageModel]:
        query = (
                select(TranscriptMessageModel)
                .where(
                        TranscriptMessageModel.conversation_id == conversation_id,
                        TranscriptMessageModel.type.in_(list(message_types))
                        )
                .options(defer(TranscriptMessageModel.audio_data))
                .order_by(TranscriptMessageModel.sequence_number.desc())
                )
        if limit > 0:
            query = query.limit(limit)

        result = await self.db.execute(query)
        return list(reversed(result.scalars().all()))


    async def get_message_count(self, conversation_id: UUID) -> int:
        """Get the count of messages for a conversation (for sequence numbering)"""
        query = select(func.count(TranscriptMessageModel.id)).where(
                TranscriptMessageModel.conversation_id == conversation_id
                )
        result = await self.db.execute(query)
        return result.scalar_one()


    async def get_message_issues(self, filter_obj: MessageIssueFilter) -> tuple[list, int]:
        """List messages that carry an admin/supervisor comment (a reported
        "issue"), newest first, with the context needed to act on them.

        Returns ``(rows, total)``; each row is labelled with the fields of
        ``ReportedIssueRead``. ``status`` defaults to 'open' for comments that
        have no tracked issue row yet.
        ``matched_note`` is the newest note matching ``search``, else None.
        The agent id and name / workflow name are resolved through the conversation's
        operator -> agent -> workflow chain (left-joined). ``topic``/``subtopic``
        follow the Conversations page: the final analysis once finalized, the
        live topic before. The query is group-scoped to the requesting user via
        the conversation.
        """
        base_filters = _issue_filters(filter_obj)
        if filter_obj.status:
            base_filters.append(_issue_status_col() == filter_obj.status)
        if filter_obj.feedback_id:
            base_filters.append(MessageFeedbackModel.id == filter_obj.feedback_id)

        rows_query = (
                _issue_joins(
                        select(
                                MessageFeedbackModel.id.label("feedback_id"),
                                TranscriptMessageModel.id.label("message_id"),
                                ConversationModel.id.label("conversation_id"),
                                AgentModel.id.label("agent_id"),
                                AgentModel.name.label("agent_name"),
                                WorkflowModel.name.label("workflow_name"),
                                TranscriptMessageModel.text,
                                TranscriptMessageModel.speaker,
                                MessageFeedbackModel.feedback_message.label("comment"),
                                MessageFeedbackModel.feedback.label("rating"),
                                _issue_status_col().label("status"),
                                UserModel.username.label("reported_by"),
                                MessageFeedbackModel.feedback_timestamp.label("reported_at"),
                                _issue_topic_col().label("conversation_topic"),
                                _issue_subtopic_col().label("conversation_subtopic"),
                                ConversationModel.conversation_date,
                                MessageIssueModel.fix_version,
                                MessageIssueModel.target_rollout_date,
                                _matched_note_col(filter_obj.search),
                                )
                        )
                .outerjoin(
                        UserModel, UserModel.id == MessageFeedbackModel.feedback_user_id
                        )
                .outerjoin(
                        WorkflowModel, WorkflowModel.id == AgentModel.workflow_id
                        )
                .where(*base_filters)
                .order_by(MessageFeedbackModel.feedback_timestamp.desc())
                .offset(filter_obj.skip)
                .limit(filter_obj.limit)
                .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
                )
        rows = (await self.db.execute(rows_query)).all()

        count_query = (
                _issue_joins(select(func.count()).select_from(MessageFeedbackModel))
                .where(*base_filters)
                .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
                )
        total = (await self.db.execute(count_query)).scalar_one()

        return list(rows), total


    async def count_message_issues_by_status(
            self, filter_obj: MessageIssueSummaryFilter
            ) -> list[tuple[str, int]]:
        """``(status, count)`` pairs over the same rows, filters and group scope
        as ``get_message_issues``."""
        status_col = _issue_status_col()
        query = (
                _issue_joins(select(status_col, func.count()).select_from(MessageFeedbackModel))
                .where(*_issue_filters(filter_obj))
                .group_by(status_col)
                .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
                )
        return [(status, count) for status, count in (await self.db.execute(query)).all()]


    async def get_or_add_issue(self, message_feedback_id: UUID) -> MessageIssueModel:
        """The tracked issue row for a comment (message_feedback row), added in the
        default status when it has none yet. Raises if the referenced comment does
        not exist."""
        await self._require_feedback(message_feedback_id)

        issue = (
                await self.db.execute(
                        select(MessageIssueModel).where(
                                MessageIssueModel.message_feedback_id == message_feedback_id
                                )
                        )
                ).scalars().first()

        if issue is None:
            issue = MessageIssueModel(
                    message_feedback_id=message_feedback_id,
                    status=DEFAULT_ISSUE_STATUS_KEY,
                    )
            self.db.add(issue)
        return issue


    async def list_issue_notes(
            self, message_feedback_id: UUID
            ) -> list[tuple[MessageIssueNoteModel, Optional[str]]]:
        await self._require_feedback(message_feedback_id)
        query = (
                select(MessageIssueNoteModel, UserModel.username)
                .outerjoin(UserModel, UserModel.id == MessageIssueNoteModel.author_user_id)
                .where(MessageIssueNoteModel.message_feedback_id == message_feedback_id)
                .order_by(MessageIssueNoteModel.created_at.asc(), MessageIssueNoteModel.id.asc())
                )
        return [(note, username) for note, username in (await self.db.execute(query)).all()]


    async def list_issue_history(
            self, message_feedback_id: UUID
            ) -> list[tuple[AuditLogModel, Optional[str]]]:
        await self._require_feedback(message_feedback_id)
        issue_id = (
                select(MessageIssueModel.id)
                .where(MessageIssueModel.message_feedback_id == message_feedback_id)
                .scalar_subquery()
                )
        query = (
                select(AuditLogModel, UserModel.username)
                .outerjoin(UserModel, UserModel.id == AuditLogModel.modified_by)
                .where(or_(
                        and_(
                                AuditLogModel.table_name == MessageIssueModel.__tablename__,
                                AuditLogModel.record_id == issue_id,
                                ),
                        and_(
                                AuditLogModel.table_name == MessageFeedbackModel.__tablename__,
                                AuditLogModel.record_id == message_feedback_id,
                                ),
                        ))
                .order_by(AuditLogModel.modified_at.asc(), AuditLogModel.id.asc())
                )
        return [(log, username) for log, username in (await self.db.execute(query)).all()]


    async def get_issue_notes_by_conversation_id(self, conversation_id: UUID) -> list[MessageIssueNoteModel]:
        query = (
                select(MessageIssueNoteModel)
                .join(MessageFeedbackModel, MessageFeedbackModel.id == MessageIssueNoteModel.message_feedback_id)
                .join(TranscriptMessageModel, TranscriptMessageModel.id == MessageFeedbackModel.message_id)
                .where(TranscriptMessageModel.conversation_id == conversation_id)
                )
        return list((await self.db.execute(query)).scalars().all())


    async def add_issue_note(
            self, message_feedback_id: UUID, author_user_id: UUID, body: str
            ) -> tuple[MessageIssueNoteModel, Optional[str]]:
        await self._require_feedback(message_feedback_id)
        note = MessageIssueNoteModel(
                message_feedback_id=message_feedback_id,
                author_user_id=author_user_id,
                body=body,
                )
        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note)
        username = await self.db.scalar(select(UserModel.username).where(UserModel.id == author_user_id))
        return note, username


    async def _require_feedback(self, message_feedback_id: UUID) -> None:
        feedback_id = (
                await self.db.execute(
                        select(MessageFeedbackModel.id)
                        .join(
                                TranscriptMessageModel,
                                TranscriptMessageModel.id == MessageFeedbackModel.message_id,
                                )
                        .join(
                                ConversationModel,
                                ConversationModel.id == TranscriptMessageModel.conversation_id,
                                )
                        .where(
                                MessageFeedbackModel.id == message_feedback_id,
                                *_visible_issue_filters(),
                                )
                        .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
                        )
                ).scalars().first()
        if not feedback_id:
            raise AppException(ErrorKey.MESSAGE_NOT_FOUND)


def _issue_status_col():
    return func.coalesce(MessageIssueModel.status, DEFAULT_ISSUE_STATUS_KEY)


def _issue_topic_col():
    return case(
            (ConversationModel.status == ConversationStatus.FINALIZED.value, ConversationAnalysisModel.topic),
            else_=ConversationModel.topic,
            )


def _issue_subtopic_col():
    return case(
            (ConversationModel.status == ConversationStatus.FINALIZED.value, ConversationAnalysisModel.subtopic),
            )


def _matching_notes(search: str):
    return select(MessageIssueNoteModel.body).where(
            MessageIssueNoteModel.message_feedback_id == MessageFeedbackModel.id,
            MessageIssueNoteModel.body.icontains(search, autoescape=True),
            )


def _matched_note_col(search: Optional[str]):
    if not search:
        return null().label("matched_note")
    return (
            _matching_notes(search)
            .order_by(MessageIssueNoteModel.created_at.desc(), MessageIssueNoteModel.id.desc())
            .limit(1)
            .scalar_subquery()
            .label("matched_note")
            )


def _visible_issue_filters() -> list:
    filters = [
            MessageFeedbackModel.feedback_message.isnot(None),
            func.trim(MessageFeedbackModel.feedback_message) != "",
            ConversationModel.is_deleted == 0,
            ]
    group_clause = get_group_scope_clause(ConversationModel)
    if group_clause is not None:
        filters.append(group_clause)
    return filters


def _issue_filters(filter_obj: MessageIssueSummaryFilter) -> list:
    filters = _visible_issue_filters()
    if filter_obj.from_date:
        filters.append(MessageFeedbackModel.feedback_timestamp >= filter_obj.from_date)
    if filter_obj.to_date:
        filters.append(MessageFeedbackModel.feedback_timestamp <= filter_obj.to_date)
    if filter_obj.agent_id:
        filters.append(AgentModel.id == filter_obj.agent_id)
    if filter_obj.topic:
        filters.append(func.lower(func.trim(_issue_topic_col())) == filter_obj.topic.strip().lower())
    if filter_obj.subtopic:
        filters.append(func.lower(func.trim(_issue_subtopic_col())) == filter_obj.subtopic.strip().lower())
    if filter_obj.search:
        filters.append(or_(
                MessageFeedbackModel.feedback_message.icontains(filter_obj.search, autoescape=True),
                _matching_notes(filter_obj.search).exists(),
                ))
    return filters


def _issue_joins(stmt):
    return (
            stmt
            .join(
                    TranscriptMessageModel,
                    TranscriptMessageModel.id == MessageFeedbackModel.message_id,
                    )
            .join(
                    ConversationModel,
                    ConversationModel.id == TranscriptMessageModel.conversation_id,
                    )
            .outerjoin(
                    MessageIssueModel,
                    MessageIssueModel.message_feedback_id == MessageFeedbackModel.id,
                    )
            .outerjoin(
                    OperatorModel,
                    OperatorModel.id == ConversationModel.operator_id,
                    )
            .outerjoin(AgentModel, AgentModel.operator_id == OperatorModel.id)
            .outerjoin(
                    ConversationAnalysisModel,
                    ConversationAnalysisModel.conversation_id == ConversationModel.id,
                    )
            )