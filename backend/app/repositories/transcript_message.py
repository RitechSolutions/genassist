from datetime import date, datetime
from typing import Iterable, List, Optional
from uuid import UUID
from injector import inject
from sqlalchemy import case, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import defer, load_only, selectinload

from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.issue_status_enum import DEFAULT_ISSUE_STATUS_KEY
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG, get_group_scope_clause
from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.db.models.message_issue import MessageIssueModel, MessageIssueNoteModel
from app.db.models.message_model import MessageFeedbackModel, TranscriptMessageModel
from app.db.models.operator import OperatorModel
from app.db.models.user import UserModel
from app.db.models.workflow import WorkflowModel
from app.repositories.db_repository import DbRepository
from app.schemas.conversation_transcript import TranscriptSegmentFeedback


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


    async def get_message_issues(
            self,
            skip: int = 0,
            limit: int = 20,
            status: Optional[str] = None,
            from_date: Optional[date] = None,
            to_date: Optional[datetime] = None,
            workflow_id: Optional[UUID] = None,
            topic: Optional[str] = None,
            subtopic: Optional[str] = None,
            ) -> tuple[list, int]:
        """List messages that carry an admin/supervisor comment (a reported
        "issue"), newest first, with the context needed to act on them.

        Returns ``(rows, total)`` where each row is the tuple
        ``(MessageFeedbackModel, TranscriptMessageModel, ConversationModel,
        reported_by_username, workflow_name, agent_id, status, issue, topic,
        subtopic)``. ``status`` defaults to 'open' for comments that have no
        tracked issue row yet, in which case ``issue`` is None. The agent id /
        workflow name are resolved through the conversation's operator -> agent
        -> workflow chain (left-joined). ``topic``/``subtopic`` follow the
        Conversations page: the final analysis once finalized, the live topic
        before. All filters (``status``, ``from_date``/``to_date`` on when the
        comment was added, ``workflow_id``, ``topic`` and ``subtopic``) are
        applied server-side. The query is group-scoped to the requesting user
        via the conversation.
        """
        status_col = _issue_status_col()
        base_filters = _issue_filters(status, from_date, to_date, workflow_id, topic, subtopic)

        rows_query = (
                _issue_joins(
                        select(
                                MessageFeedbackModel,
                                TranscriptMessageModel,
                                ConversationModel,
                                UserModel.username,
                                WorkflowModel.name,
                                AgentModel.id,
                                status_col,
                                MessageIssueModel,
                                _issue_topic_col(),
                                _issue_subtopic_col(),
                                )
                        )
                .outerjoin(
                        UserModel, UserModel.id == MessageFeedbackModel.feedback_user_id
                        )
                .outerjoin(
                        WorkflowModel, WorkflowModel.id == AgentModel.workflow_id
                        )
                .where(*base_filters)
                .options(
                        load_only(TranscriptMessageModel.text, TranscriptMessageModel.speaker),
                        load_only(ConversationModel.conversation_date),
                        )
                .order_by(MessageFeedbackModel.feedback_timestamp.desc())
                .offset(skip)
                .limit(limit)
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
            self,
            from_date: Optional[date] = None,
            to_date: Optional[datetime] = None,
            workflow_id: Optional[UUID] = None,
            topic: Optional[str] = None,
            subtopic: Optional[str] = None,
            ) -> list[tuple[str, int]]:
        """``(status, count)`` pairs over the same rows, filters and group scope
        as ``get_message_issues``."""
        status_col = _issue_status_col()
        query = (
                _issue_joins(select(status_col, func.count()).select_from(MessageFeedbackModel))
                .where(*_issue_filters(None, from_date, to_date, workflow_id, topic, subtopic))
                .group_by(status_col)
                .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
                )
        return [(status, count) for status, count in (await self.db.execute(query)).all()]


    async def get_issue(self, message_feedback_id: UUID) -> Optional[MessageIssueModel]:
        return (
                await self.db.execute(
                        select(MessageIssueModel).where(
                                MessageIssueModel.message_feedback_id == message_feedback_id
                                )
                        )
                ).scalars().first()


    async def upsert_issue(
            self, message_feedback_id: UUID, values: dict
            ) -> MessageIssueModel:
        """Create or update the tracked issue row for a comment (message_feedback
        row) with ``values`` as given. Raises if the referenced comment does not
        exist."""
        await self._require_feedback(message_feedback_id)

        issue = await self.get_issue(message_feedback_id)

        if issue:
            for key, value in values.items():
                setattr(issue, key, value)
        else:
            issue = MessageIssueModel(
                    message_feedback_id=message_feedback_id,
                    **{"status": DEFAULT_ISSUE_STATUS_KEY, **values},
                    )
            self.db.add(issue)

        await self.db.flush()
        await self.db.refresh(issue)
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
                        .where(MessageFeedbackModel.id == message_feedback_id, *_issue_filters())
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


def _issue_filters(
        status: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[datetime] = None,
        workflow_id: Optional[UUID] = None,
        topic: Optional[str] = None,
        subtopic: Optional[str] = None,
        ) -> list:
    filters = [
            MessageFeedbackModel.feedback_message.isnot(None),
            func.trim(MessageFeedbackModel.feedback_message) != "",
            ConversationModel.is_deleted == 0,
            ]
    if status:
        filters.append(_issue_status_col() == status)
    if from_date:
        filters.append(MessageFeedbackModel.feedback_timestamp >= from_date)
    if to_date:
        filters.append(MessageFeedbackModel.feedback_timestamp <= to_date)
    if workflow_id:
        filters.append(AgentModel.workflow_id == workflow_id)
    if topic:
        filters.append(func.lower(func.trim(_issue_topic_col())) == topic.strip().lower())
    if subtopic:
        filters.append(func.lower(func.trim(_issue_subtopic_col())) == subtopic.strip().lower())

    group_clause = get_group_scope_clause(ConversationModel)
    if group_clause is not None:
        filters.append(group_clause)
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