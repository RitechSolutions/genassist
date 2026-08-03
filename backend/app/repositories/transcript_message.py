from datetime import date, datetime
from typing import List, Optional
from uuid import UUID
from injector import inject
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.issue_status_enum import IssueStatus, TERMINAL_ISSUE_STATUSES
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG, get_group_scope_clause
from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationModel
from app.db.models.message_issue import MessageIssueModel
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
        await self.db.commit()
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
            await self.db.commit()
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
            await self.db.commit()
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
        await self.db.commit()


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
            ) -> tuple[list, int]:
        """List messages that carry an admin/supervisor comment (a reported
        "issue"), newest first, with the context needed to act on them.

        Returns ``(rows, total)`` where each row is the tuple
        ``(MessageFeedbackModel, TranscriptMessageModel, ConversationModel,
        reported_by_username, workflow_name, agent_id, status)``. ``status``
        defaults to 'open' for comments that have no tracked issue row yet. The
        agent id / workflow name are resolved through the conversation's
        operator -> agent -> workflow chain (left-joined). All filters
        (``status``, ``from_date``/``to_date`` on when the comment was added, and
        ``workflow_id``) are applied server-side. The query is group-scoped to
        the requesting user via the conversation.
        """
        status_col = func.coalesce(
                MessageIssueModel.status, IssueStatus.OPEN.value
                )

        base_filters = [
                MessageFeedbackModel.feedback_message.isnot(None),
                func.trim(MessageFeedbackModel.feedback_message) != "",
                ConversationModel.is_deleted == 0,
                ]
        if status:
            base_filters.append(status_col == status)
        # Time range filters the moment the comment was added (reported time).
        if from_date:
            base_filters.append(MessageFeedbackModel.feedback_timestamp >= from_date)
        if to_date:
            base_filters.append(MessageFeedbackModel.feedback_timestamp <= to_date)
        if workflow_id:
            base_filters.append(AgentModel.workflow_id == workflow_id)

        # Apply conversation group-scoping explicitly and bypass the implicit
        # do_orm_execute listener (see app/db/events/group_scope.py) so the joins
        # used only to resolve display fields are not themselves group-filtered.
        group_clause = get_group_scope_clause(ConversationModel)
        if group_clause is not None:
            base_filters.append(group_clause)

        def _core_joins(stmt):
            """Joins shared by the rows and count queries (drive filtering).

            Operator/Agent are left-joined here (not just in the rows query) so the
            ``workflow_id`` filter applies to the count too. They stay one-to-one
            per feedback row, so the count is unaffected when no filter is set.
            """
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
                    )

        rows_query = (
                _core_joins(
                        select(
                                MessageFeedbackModel,
                                TranscriptMessageModel,
                                ConversationModel,
                                UserModel.username,
                                WorkflowModel.name,
                                AgentModel.id,
                                status_col,
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
                .offset(skip)
                .limit(limit)
                .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
                )
        rows = (await self.db.execute(rows_query)).all()

        count_query = (
                _core_joins(select(func.count()).select_from(MessageFeedbackModel))
                .where(*base_filters)
                .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
                )
        total = (await self.db.execute(count_query)).scalar_one()

        return list(rows), total


    async def set_issue_status(
            self, message_feedback_id: UUID, status: str
            ) -> MessageIssueModel:
        """Upsert the tracked resolution status for a comment (message_feedback
        row). Stamps resolved_by/resolved_at on terminal statuses and clears them
        otherwise. Raises if the referenced comment does not exist."""
        from datetime import datetime, timezone

        feedback = (
                await self.db.execute(
                        select(MessageFeedbackModel).where(
                                MessageFeedbackModel.id == message_feedback_id
                                )
                        )
                ).scalars().first()
        if not feedback:
            raise AppException(ErrorKey.MESSAGE_NOT_FOUND)

        is_terminal = status in {s.value for s in TERMINAL_ISSUE_STATUSES}
        resolved_at = datetime.now(timezone.utc) if is_terminal else None
        resolved_by = get_current_user_id() if is_terminal else None

        existing = (
                await self.db.execute(
                        select(MessageIssueModel).where(
                                MessageIssueModel.message_feedback_id == message_feedback_id
                                )
                        )
                ).scalars().first()

        if existing:
            existing.status = status
            existing.resolved_at = resolved_at
            existing.resolved_by = resolved_by
            issue = existing
        else:
            issue = MessageIssueModel(
                    message_feedback_id=message_feedback_id,
                    status=status,
                    resolved_at=resolved_at,
                    resolved_by=resolved_by,
                    )
            self.db.add(issue)

        await self.db.commit()
        await self.db.refresh(issue)
        return issue